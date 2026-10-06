from django.db.models import Q, Sum
from django.db.models.functions import Upper
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clientes.models import Cliente
from apps.products.forms import BrandForm, ClaseForm, LineaForm, UnitMeasureForm
from apps.products.models import Producto, Subcategoria
from apps.core.parametros import id_valido, ids_validos
from apps.products.services import resolver_lista_precio_cliente, resolver_precio_autorizado
from apps.api.permissions import PuedeEditarProductos, RequierePermisos
from apps.api.serializers.products import ActualizarCostoSerializer, OptionSerializer


class SubcategoriesByCategoryView(ListAPIView):
    """Subcategorías activas filtradas por categoría."""
    serializer_class = OptionSerializer
    pagination_class = None

    def get_queryset(self):
        category_id = id_valido(self.request.query_params.get("category"))
        if not category_id:
            return Subcategoria.objects.none()
        return (
            Subcategoria.objects
            .filter(categoria_id=category_id, is_active=True)
            .order_by("nombre")
        )


class BrandQuickCreateView(APIView):
    """Alta rápida de Marca desde el formulario de producto."""

    permission_classes = [PuedeEditarProductos]

    def post(self, request):
        form = BrandForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=400)
        obj = form.save()
        return Response({"value": obj.id, "label": obj.nombre}, status=201)


class LineaQuickCreateView(APIView):
    """Alta rápida de Línea desde el formulario de producto."""

    permission_classes = [PuedeEditarProductos]

    def post(self, request):
        form = LineaForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=400)
        obj = form.save()
        return Response({"value": obj.id, "label": obj.nombre}, status=201)


class ClaseQuickCreateView(APIView):
    """Alta rápida de Clase desde el formulario de producto."""

    permission_classes = [PuedeEditarProductos]

    def post(self, request):
        form = ClaseForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=400)
        obj = form.save()
        return Response({"value": obj.id, "label": obj.nombre}, status=201)


class ProductoBuscarView(APIView):
    """Busca productos por folio, SKU, código de barras o nombre. Pensado
    para reemplazar un <select> en catálogos grandes (~300 mil productos),
    donde renderizar todas las opciones no es viable.

    Con `?almacen=<id>` (usado por el buscador de traspasos) solo devuelve
    productos con existencia disponible (>0) en ese almacén — no tiene
    sentido ofrecer para traspaso algo que no está en stock ahí — e incluye
    `disponible` con esa cantidad.

    Con `?cliente=<id>` y/o `?precio_almacen=<id>` (usados por ventas)
    `precio_venta` deja de ser el precio_venta plano del producto y pasa a
    ser el resuelto para la lista de precios de ese cliente (o "PUBLICO" si
    no tiene una propia) y esa sucursal -ver
    apps.products.services.resolver_precio_linea-, que sí respeta los
    precios específicos por sucursal (ProductoPrecio.almacen) que el precio
    plano no conoce. Es un parámetro aparte de "almacen" a propósito: no
    debe activar el filtro de existencia de arriba, que es solo para
    traspasos."""

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 3:
            return Response([])

        productos = Producto.objects.filter(is_active=True).filter(
            Q(folio__icontains=q)
            | Q(sku__icontains=q)
            | Q(codigo_barras__icontains=q)
            | Q(nombre__icontains=q)
        )

        almacen_crudo = request.query_params.get("almacen", "").strip()
        almacen_id = id_valido(almacen_crudo)
        con_existencia = bool(almacen_crudo)
        if con_existencia and almacen_id is None:
            return Response([])
        if con_existencia:
            productos = productos.filter(
                lotes__almacen_id=almacen_id, lotes__cantidad_disponible__gt=0
            ).annotate(
                disponible=Sum(
                    "lotes__cantidad_disponible",
                    filter=Q(lotes__almacen_id=almacen_id),
                )
            )

        # Solo se resuelve el precio por lista/sucursal si el llamador manda
        # alguno de estos dos parámetros (hoy, solo ventas): así compras,
        # traspasos, comisiones, etc. no pagan consultas extra que no usan
        # y su resultado no cambia.
        cliente_id = id_valido(request.query_params.get("cliente"))
        precio_almacen_id = id_valido(request.query_params.get("precio_almacen"))
        contexto_venta = bool(cliente_id or precio_almacen_id)
        lista_precio = None
        if contexto_venta:
            cliente = Cliente.objects.filter(pk=cliente_id).select_related("lista_precio").first() if cliente_id else None
            lista_precio = resolver_lista_precio_cliente(cliente)

        productos = productos.order_by("nombre")[:20]
        data = []
        for p in productos:
            precio_venta = (
                resolver_precio_autorizado(p, lista_precio, precio_almacen_id) if contexto_venta else p.precio_venta
            )
            data.append({
                "id": p.id,
                "folio": p.folio,
                "sku": p.sku,
                "nombre": p.nombre,
                "precio_venta": str(precio_venta),
                "precio_costo": str(p.precio_costo),
                **({"disponible": str(p.disponible)} if con_existencia else {}),
            })
        return Response(data)


class ProductoPreciosPorClienteView(APIView):
    """Re-resuelve el precio_venta de una lista de productos ya elegidos en
    un formset (ventas/cotizaciones) cuando el cliente de la operación
    cambia DESPUÉS de haberlos agregado: ProductoBuscarView solo resuelve
    el precio en el momento de buscar/elegir el producto, así que si el
    cajero cambia de cliente sin volver a buscar cada línea, el precio
    capturado se queda pegado al del cliente anterior -ver
    producto-search.js, que llama aquí al detectar un "change" en el
    campo de cliente-. Misma lógica de resolución que ProductoBuscarView,
    solo que por id en vez de por texto."""

    def post(self, request):
        datos = request.data if isinstance(request.data, dict) else {}
        ids = ids_validos(datos.get("ids", []))
        if not ids:
            return Response({"precios": {}})

        cliente_id = id_valido(datos.get("cliente"))
        precio_almacen_id = id_valido(datos.get("precio_almacen"))
        cliente = Cliente.objects.filter(pk=cliente_id).select_related("lista_precio").first() if cliente_id else None
        lista_precio = resolver_lista_precio_cliente(cliente)

        precios = {}
        for p in Producto.objects.filter(pk__in=ids, is_active=True):
            precio_venta = resolver_precio_autorizado(p, lista_precio, precio_almacen_id)
            precios[str(p.id)] = str(precio_venta)
        return Response({"precios": precios})


class ProductoResolverSkusView(APIView):
    """Resuelve una lista de SKUs a productos (coincidencia exacta,
    insensible a mayúsculas/minúsculas). Pensado para la carga por lista
    (pegas SKU + cantidad por línea) de Compras, Ventas y Cotizaciones.

    Con `almacen` en el body (ventas/cotizaciones) solo se ofrecen los
    productos con existencia ahí -mismo criterio que ProductoBuscarView-;
    los que sí existen como producto pero sin stock en esa sucursal se
    reportan aparte en `sin_existencia`, distinto de `no_encontrados`
    (SKU que no corresponde a ningún producto). Con `cliente` y/o
    `precio_almacen` se resuelve `precio_venta` contra la lista de
    precios de ese cliente, igual que ProductoBuscarView."""

    def post(self, request):
        datos = request.data if isinstance(request.data, dict) else {}
        skus = datos.get("skus", [])
        if not isinstance(skus, list):
            return Response({"detail": "Se espera una lista de SKUs."}, status=400)

        skus_norm = [str(s).strip().upper() for s in skus if str(s).strip()]
        if not skus_norm:
            return Response({"productos": [], "no_encontrados": [], "sin_existencia": []})

        almacen_crudo = str(datos.get("almacen") or "").strip()
        almacen_id = id_valido(almacen_crudo)
        if almacen_crudo and almacen_id is None:
            return Response({"detail": "Almacén inválido."}, status=400)

        productos_qs = (
            Producto.objects.filter(is_active=True)
            .exclude(tipo=Producto.TipoProducto.PAQUETE)
            .annotate(sku_upper=Upper("sku"))
            .filter(sku_upper__in=set(skus_norm))
        )
        if almacen_id:
            productos_qs = productos_qs.annotate(
                disponible=Sum("lotes__cantidad_disponible", filter=Q(lotes__almacen_id=almacen_id))
            )

        productos = list(productos_qs)
        por_sku = {p.sku.upper(): p for p in productos}
        no_encontrados = [s for s in dict.fromkeys(skus_norm) if s not in por_sku]

        sin_existencia = []
        if almacen_id:
            con_existencia = [p for p in productos if (p.disponible or 0) > 0]
            sin_existencia = [p.sku for p in productos if not ((p.disponible or 0) > 0)]
            productos = con_existencia

        cliente_id = id_valido(datos.get("cliente"))
        precio_almacen_id = id_valido(datos.get("precio_almacen"))
        contexto_venta = bool(cliente_id or precio_almacen_id)
        lista_precio = None
        if contexto_venta:
            cliente = Cliente.objects.filter(pk=cliente_id).select_related("lista_precio").first() if cliente_id else None
            lista_precio = resolver_lista_precio_cliente(cliente)

        data = []
        for p in productos:
            precio_venta = (
                resolver_precio_autorizado(p, lista_precio, precio_almacen_id) if contexto_venta else p.precio_venta
            )
            data.append({
                "id": p.id,
                "folio": p.folio,
                "sku": p.sku,
                "nombre": p.nombre,
                "precio_costo": str(p.precio_costo),
                "precio_venta": str(precio_venta),
            })
        return Response({"productos": data, "no_encontrados": no_encontrados, "sin_existencia": sin_existencia})


class ProductoActualizarCostoView(APIView):
    """Actualiza el precio de costo de un producto desde la orden de compra,
    cuando el precio pagado al proveedor supera el costo anterior registrado.
    Exige el mismo permiso que editar el producto: cambiar el costo también
    recalcula los precios de lista con % de utilidad (ver
    Producto._recalcular_precios_por_utilidad)."""

    permission_classes = [RequierePermisos]
    permisos_requeridos = ("products.change_producto",)

    def post(self, request):
        serializer = ActualizarCostoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"detail": "Datos inválidos.", "errors": serializer.errors}, status=400)

        producto = serializer.validated_data["producto"]
        producto.precio_costo = serializer.validated_data["precio_costo"]
        producto.save(update_fields=["precio_costo", "updated_at", "updated_by"])
        return Response({"precio_costo": str(producto.precio_costo)})


class UnitMeasureQuickCreateView(APIView):
    """Alta rápida de Unidad de medida desde el formulario de producto."""

    permission_classes = [PuedeEditarProductos]

    def post(self, request):
        form = UnitMeasureForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=400)
        obj = form.save()
        return Response({"value": obj.id, "label": str(obj)}, status=201)
