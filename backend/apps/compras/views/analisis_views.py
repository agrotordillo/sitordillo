from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Case, DecimalField, ExpressionWrapper, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, ExtractMonth, ExtractYear, Greatest, NullIf
from django.utils import timezone
from django.views.generic import ListView, TemplateView

from apps.compras.models import OrdenCompra, OrdenCompraDetalle
from apps.core.parametros import entero, fecha, filtrar_por_id
from apps.core.scoping import almacenes_visibles
from apps.products.busqueda import q_busqueda_producto
from apps.products.models import Almacen, Linea, Marca

# Órdenes que no representan una compra: nunca se confirmó o no se concretó.
ESTATUS_SIN_COMPRA = (OrdenCompra.Estatus.BORRADOR, OrdenCompra.Estatus.CANCELADA)

# Mismo cálculo que OrdenCompraDetalle.cantidad_facturable, pero expresado
# a nivel SQL para poder sumarlo en un solo aggregate() sin traer cada fila
# a Python: ya recibido algo, lo facturable es recibida - merma (nunca
# negativo); si no, es lo ordenado.
_CANTIDAD_FACTURABLE_EXPR = Case(
    When(
        cantidad_recibida__gt=0,
        then=Greatest(F("cantidad_recibida") - F("cantidad_merma"), Value(Decimal("0.00"))),
    ),
    default=F("cantidad"),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)
IMPORTE_EXPR = ExpressionWrapper(
    _CANTIDAD_FACTURABLE_EXPR * F("precio_unitario"),
    output_field=DecimalField(max_digits=16, decimal_places=2),
)
# Igual que Proveedor.display_name (nombre_comercial si lo trae, si no
# nombre_fiscal): nombre_comercial es blank="", no null, así que hace
# falta NullIf para que Coalesce lo salte cuando está vacío.
_PROVEEDOR_NOMBRE_EXPR = Coalesce(
    NullIf(F("orden_compra__proveedor__nombre_comercial"), Value("")),
    F("orden_compra__proveedor__nombre_fiscal"),
)
# Igual cálculo que OrdenCompraDetalle.precio_neto: una orden cargada desde
# CFDI ya viene neta (cfdi_uuid no nulo); si no, se descuenta el % base del
# proveedor congelado en la orden.
PRECIO_NETO_EXPR = Case(
    When(orden_compra__cfdi_uuid__isnull=False, then=F("precio_unitario")),
    default=F("precio_unitario") * (Value(Decimal("1")) - F("orden_compra__descuento_base_pct") / Value(Decimal("100"))),
    output_field=DecimalField(max_digits=14, decimal_places=4),
)

# Columna del encabezado (ver ?ordenar=<clave> o ?ordenar=-<clave>) -> qué
# ordenar: un nombre de campo, o una expresión ya armada arriba cuando el
# valor mostrado no es un campo directo (Importe, Precio neto, Proveedor).
ORDEN_CAMPOS = {
    "fecha": "orden_compra__fecha_orden",
    "documento": "orden_compra__documento",
    "proveedor": _PROVEEDOR_NOMBRE_EXPR,
    "codigo": "producto__sku",
    "producto": "producto__nombre",
    "cantidad": "cantidad",
    "costo": "precio_unitario",
    "importe": IMPORTE_EXPR,
    "recibida": "cantidad_recibida",
    "precio_neto": PRECIO_NETO_EXPR,
    "estatus": "orden_compra__estatus",
}


class AnalisisCompraProductoListView(PermissionRequiredMixin, ListView):
    """Historial de compra por producto: a diferencia de Surtimiento por
    sucursal (que solo dice qué está por debajo del mínimo ahora), este
    reporte muestra cada línea de compra real -proveedor, número de
    factura, precio pagado, fecha- para poder analizar a quién y a qué
    precio se le ha comprado un producto a lo largo del tiempo."""

    permission_required = "compras.view_ordencompradetalle"
    model = OrdenCompraDetalle
    template_name = "compras/analisis_compra_producto_list.html"
    context_object_name = "detalles"
    extra_context = {"active_module": "purchases"}
    paginate_by = 50

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("producto", "orden_compra", "orden_compra__proveedor")
            # Solo compras reales, igual que el análisis anual: un borrador
            # nunca se confirmó y una cancelada no se concretó (B30).
            .exclude(orden_compra__estatus__in=ESTATUS_SIN_COMPRA)
        )
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            qs = qs.filter(orden_compra__almacen_destino__in=visibles)

        buscar = self.request.GET.get("q", "").strip()
        if buscar:
            qs = qs.filter(
                q_busqueda_producto(buscar, "producto__")
                | Q(orden_compra__proveedor__nombre_comercial__icontains=buscar)
                | Q(orden_compra__proveedor__nombre_fiscal__icontains=buscar)
                | Q(orden_compra__proveedor__rfc__icontains=buscar)
                | Q(orden_compra__documento__icontains=buscar)
            )

        fecha_desde = fecha(self.request.GET.get("fecha_desde"))
        if fecha_desde:
            qs = qs.filter(orden_compra__fecha_orden__gte=fecha_desde)
        fecha_hasta = fecha(self.request.GET.get("fecha_hasta"))
        if fecha_hasta:
            qs = qs.filter(orden_compra__fecha_orden__lte=fecha_hasta)

        qs = filtrar_por_id(qs, "orden_compra__almacen_destino_id", self.request.GET.get("almacen"))
        qs = filtrar_por_id(qs, "producto__linea_id", self.request.GET.get("linea"))
        qs = filtrar_por_id(qs, "producto__marca_id", self.request.GET.get("marca"))

        campo, descendente = self._ordenar_actual()
        if campo:
            expr = ORDEN_CAMPOS[campo]
            expr = F(expr) if isinstance(expr, str) else expr
            orden_expr = expr.desc(nulls_last=True) if descendente else expr.asc(nulls_last=True)
            # "pk" de desempate: sin esto, filas con el mismo valor ordenado
            # (p. ej. mismo estatus) podrían cambiar de orden entre páginas.
            return qs.order_by(orden_expr, "pk")

        return qs.order_by("-orden_compra__fecha_orden", "producto__nombre")

    def _ordenar_actual(self):
        """(campo, descendente) según ?ordenar=<clave> o ?ordenar=-<clave>
        en la URL; (None, False) si no viene o no es una clave válida."""
        valor = self.request.GET.get("ordenar", "").strip()
        descendente = valor.startswith("-")
        campo = valor[1:] if descendente else valor
        if campo not in ORDEN_CAMPOS:
            return None, False
        return campo, descendente

    def _url_ordenar(self, campo):
        """URL de esta misma pantalla con los filtros actuales, ordenando
        por `campo`: asciende si no era la columna activa o estaba
        descendente, desciende si ya ascendía por ella. Siempre quita
        "page": cambiar de orden reinicia la paginación."""
        campo_actual, descendente_actual = self._ordenar_actual()
        if campo_actual == campo and not descendente_actual:
            nuevo_valor = f"-{campo}"
        else:
            nuevo_valor = campo
        parametros = self.request.GET.copy()
        parametros["ordenar"] = nuevo_valor
        parametros.pop("page", None)
        return f"?{parametros.urlencode()}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["fecha_desde"] = self.request.GET.get("fecha_desde", "")
        context["fecha_hasta"] = self.request.GET.get("fecha_hasta", "")
        context["almacen_id"] = self.request.GET.get("almacen", "")
        context["linea_id"] = self.request.GET.get("linea", "")
        context["marca_id"] = self.request.GET.get("marca", "")
        context["hay_filtros"] = bool(
            context["q"] or context["fecha_desde"] or context["fecha_hasta"]
            or context["almacen_id"] or context["linea_id"] or context["marca_id"]
        )

        campo_orden, descendente = self._ordenar_actual()
        context["ordenar_campo"] = campo_orden
        context["ordenar_descendente"] = descendente
        context["ordenar_urls"] = {campo: self._url_ordenar(campo) for campo in ORDEN_CAMPOS}

        almacenes = Almacen.objects.filter(is_active=True)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))
        context["almacenes"] = almacenes.order_by("nombre")
        context["lineas"] = Linea.objects.filter(is_active=True).order_by("nombre")
        context["marcas"] = Marca.objects.filter(is_active=True).order_by("nombre")

        # Sobre el queryset filtrado completo (no la página actual): igual
        # patrón que apps.inventario.views.movimiento_costo_views.
        totales = self.get_queryset().aggregate(
            total_cantidad=Sum("cantidad"),
            total_recibida=Sum("cantidad_recibida"),
            total_importe=Sum(IMPORTE_EXPR),
        )
        context["total_cantidad"] = totales["total_cantidad"] or Decimal("0.00")
        context["total_recibida"] = totales["total_recibida"] or Decimal("0.00")
        # Igual filosofía que OrdenCompra.descuento_monto: se redondea una
        # sola vez aquí, sobre el valor preciso ya sumado -no se suma lo
        # que ya se redondeó renglón por renglón en pantalla (Importe)-,
        # para no arrastrar error de redondeo.
        total_importe = totales["total_importe"] or Decimal("0.00")
        context["total_importe"] = total_importe.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return context


MESES_ABREV = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}


class AnalisisCompraAnualListView(PermissionRequiredMixin, TemplateView):
    """Tabla pivote producto × mes: cuánto se recibió de cada producto en
    cada mes del año seleccionado, más el total del año. Solo cuenta lo
    que realmente entró al almacén (cantidad_recibida), no lo ordenado
    pero aún no recibido, y solo de órdenes reales -se excluyen borrador
    (nunca se confirmó) y cancelada (no se concretó)."""

    permission_required = "compras.view_ordencompradetalle"
    template_name = "compras/analisis_compra_anual_list.html"
    extra_context = {"active_module": "purchases"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        anios_disponibles = list(
            OrdenCompra.objects.annotate(anio=ExtractYear("fecha_orden"))
            .order_by("-anio")
            .values_list("anio", flat=True)
            .distinct()
        )
        anio_actual = timezone.localdate().year
        anio = entero(self.request.GET.get("anio"), minimo=1, maximo=9999) or (
            anios_disponibles[0] if anios_disponibles else anio_actual
        )

        producto_id = self.request.GET.get("producto", "").strip()
        proveedor_id = self.request.GET.get("proveedor", "").strip()
        almacen_id = self.request.GET.get("almacen", "").strip()

        detalles = (
            OrdenCompraDetalle.objects.filter(orden_compra__fecha_orden__year=anio)
            .exclude(orden_compra__estatus__in=ESTATUS_SIN_COMPRA)
        )
        detalles = filtrar_por_id(detalles, "producto_id", producto_id)
        detalles = filtrar_por_id(detalles, "orden_compra__proveedor_id", proveedor_id)
        detalles = filtrar_por_id(detalles, "orden_compra__almacen_destino_id", almacen_id)
        # El selector ya solo ofrece las sucursales del usuario; los datos
        # también se limitan a ellas (mismo criterio que B10).
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            detalles = detalles.filter(orden_compra__almacen_destino__in=visibles)

        filas_planas = (
            detalles.annotate(mes=ExtractMonth("orden_compra__fecha_orden"))
            .values("producto_id", "producto__nombre", "producto__sku", "mes")
            .annotate(total_mes=Sum("cantidad_recibida"))
            .order_by("producto__nombre")
        )

        productos = {}
        for fila in filas_planas:
            producto = productos.setdefault(
                fila["producto_id"],
                {
                    "nombre": fila["producto__nombre"],
                    "sku": fila["producto__sku"],
                    "meses": [0] * 12,
                    "total": 0,
                },
            )
            producto["meses"][fila["mes"] - 1] = fila["total_mes"]
            producto["total"] += fila["total_mes"]

        filas = sorted(productos.values(), key=lambda p: p["nombre"])

        almacenes = Almacen.objects.filter(is_active=True)
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))

        context["filas"] = filas
        context["meses"] = list(MESES_ABREV.values())
        context["anio"] = anio
        context["anios_disponibles"] = anios_disponibles
        context["producto_id"] = producto_id
        context["proveedor_id"] = proveedor_id
        context["almacen_id"] = almacen_id
        context["almacenes"] = almacenes
        context["hay_filtros"] = bool(producto_id or proveedor_id or almacen_id)
        return context
