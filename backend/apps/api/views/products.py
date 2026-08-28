from decimal import Decimal, InvalidOperation

from django.db.models import Q, Sum
from django.db.models.functions import Upper
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.forms import BrandForm, UnitMeasureForm
from apps.products.models import Producto, Subcategoria
from apps.api.serializers.products import OptionSerializer


class SubcategoriesByCategoryView(ListAPIView):
    """Subcategorías activas filtradas por categoría."""
    serializer_class = OptionSerializer
    pagination_class = None
    permission_classes = [AllowAny]

    def get_queryset(self):
        category_id = self.request.query_params.get("category")
        if not category_id:
            return Subcategoria.objects.none()
        return (
            Subcategoria.objects
            .filter(categoria_id=category_id, is_active=True)
            .order_by("nombre")
        )


class BrandQuickCreateView(APIView):
    """Alta rápida de Marca desde el formulario de producto."""
    permission_classes = [AllowAny]

    def post(self, request):
        form = BrandForm(request.data)
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
    `disponible` con esa cantidad."""
    permission_classes = [AllowAny]

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

        almacen_id = request.query_params.get("almacen", "").strip()
        con_existencia = bool(almacen_id)
        if con_existencia:
            productos = productos.filter(
                lotes__almacen_id=almacen_id, lotes__cantidad_disponible__gt=0
            ).annotate(
                disponible=Sum(
                    "lotes__cantidad_disponible",
                    filter=Q(lotes__almacen_id=almacen_id),
                )
            )

        productos = productos.order_by("nombre")[:20]
        data = [
            {
                "id": p.id,
                "folio": p.folio,
                "sku": p.sku,
                "nombre": p.nombre,
                "precio_venta": str(p.precio_venta),
                "precio_costo": str(p.precio_costo),
                **({"disponible": str(p.disponible)} if con_existencia else {}),
            }
            for p in productos
        ]
        return Response(data)


class ProductoResolverSkusView(APIView):
    """Resuelve una lista de SKUs a productos (coincidencia exacta,
    insensible a mayúsculas/minúsculas). Pensado para la carga por lista de
    Compras: pegas SKU + cantidad por línea y esto encuentra el producto de
    cada SKU en un solo viaje al servidor."""
    permission_classes = [AllowAny]

    def post(self, request):
        skus = request.data.get("skus", [])
        if not isinstance(skus, list):
            return Response({"detail": "Se espera una lista de SKUs."}, status=400)

        skus_norm = [str(s).strip().upper() for s in skus if str(s).strip()]
        if not skus_norm:
            return Response({"productos": [], "no_encontrados": []})

        productos = list(
            Producto.objects.filter(is_active=True)
            .exclude(tipo=Producto.TipoProducto.PAQUETE)
            .annotate(sku_upper=Upper("sku"))
            .filter(sku_upper__in=set(skus_norm))
        )
        por_sku = {p.sku.upper(): p for p in productos}
        no_encontrados = [s for s in dict.fromkeys(skus_norm) if s not in por_sku]

        data = [
            {
                "id": p.id,
                "folio": p.folio,
                "sku": p.sku,
                "nombre": p.nombre,
                "precio_costo": str(p.precio_costo),
            }
            for p in productos
        ]
        return Response({"productos": data, "no_encontrados": no_encontrados})


class ProductoActualizarCostoView(APIView):
    """Actualiza el precio de costo de un producto desde la orden de compra,
    cuando el precio pagado al proveedor supera el costo anterior registrado."""
    permission_classes = [AllowAny]

    def post(self, request):
        producto_id = request.data.get("producto")
        precio_costo = request.data.get("precio_costo")
        if not producto_id or precio_costo is None:
            return Response({"detail": "Faltan datos."}, status=400)

        try:
            producto = Producto.objects.get(pk=producto_id)
        except (Producto.DoesNotExist, ValueError):
            return Response({"detail": "Producto no encontrado."}, status=404)

        try:
            nuevo_costo = Decimal(str(precio_costo))
        except InvalidOperation:
            return Response({"detail": "Precio de costo inválido."}, status=400)
        if nuevo_costo < 0:
            return Response({"detail": "El precio de costo no puede ser negativo."}, status=400)

        producto.precio_costo = nuevo_costo
        producto.save(update_fields=["precio_costo"])
        return Response({"precio_costo": str(producto.precio_costo)})


class UnitMeasureQuickCreateView(APIView):
    """Alta rápida de Unidad de medida desde el formulario de producto."""
    permission_classes = [AllowAny]

    def post(self, request):
        form = UnitMeasureForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=400)
        obj = form.save()
        return Response({"value": obj.id, "label": str(obj)}, status=201)
