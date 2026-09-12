import openpyxl
from django.contrib.auth.decorators import permission_required
from django.db.models import DecimalField, OuterRef, Q, Subquery
from django.http import HttpResponse
from django.utils import timezone

from apps.products.models import Producto, ProductoPrecio
from apps.products.views.product_views import LISTAS_PRECIO_TABLA

ENCABEZADOS = [
    "Folio", "SKU", "Código de barras", "Nombre", "Tipo", "Estatus",
    "Categoría", "Subcategoría", "Línea", "Clase", "Marca", "Proveedor", "Código de proveedor",
    "Unidad de medida", "IVA", "Tasa IVA (%)", "Aplica IEPS", "Tasa IEPS (%)",
    "Método de costeo", "Precio de costo", "Precio de venta (general)",
] + [nombre.title() for nombre, _ in LISTAS_PRECIO_TABLA] + [
    "Stock mínimo", "Stock máximo", "Peso (kg)", "Días de reserva",
]


@permission_required("products.view_producto", raise_exception=True)
def producto_exportar_excel_view(request):
    """Descarga en Excel el mismo listado de Productos que se ve en
    pantalla -respeta los filtros de búsqueda, marca, línea, categoría y
    clase si se llega desde ahí-, con toda su información incluidos los 5
    precios generales de lista (los mismos que se muestran como columnas
    en el listado)."""
    queryset = Producto.objects.select_related(
        "categoria", "subcategoria", "linea", "clase", "marca", "proveedor", "unidad_medida",
    ).order_by("nombre")

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(Q(folio__icontains=q) | Q(sku__icontains=q) | Q(nombre__icontains=q))

    marca_id = request.GET.get("marca", "").strip()
    if marca_id:
        queryset = queryset.filter(marca_id=marca_id)

    linea_id = request.GET.get("linea", "").strip()
    if linea_id:
        queryset = queryset.filter(linea_id=linea_id)

    categoria_id = request.GET.get("categoria", "").strip()
    if categoria_id:
        queryset = queryset.filter(categoria_id=categoria_id)

    clase_id = request.GET.get("clase", "").strip()
    if clase_id:
        queryset = queryset.filter(clase_id=clase_id)

    annotations = {
        campo: Subquery(
            ProductoPrecio.objects.filter(
                producto_id=OuterRef("pk"), lista_precio__nombre=nombre, almacen__isnull=True,
            ).values("precio_con_impuesto")[:1],
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        for nombre, campo in LISTAS_PRECIO_TABLA
    }
    queryset = queryset.annotate(**annotations)

    workbook = openpyxl.Workbook()
    hoja = workbook.active
    hoja.title = "Productos"
    hoja.append(ENCABEZADOS)

    for producto in queryset.iterator():
        hoja.append([
            producto.folio,
            producto.sku,
            producto.codigo_barras or "",
            producto.nombre,
            producto.get_tipo_display(),
            "Activo" if producto.is_active else "Inactivo",
            producto.categoria.nombre if producto.categoria_id else "",
            producto.subcategoria.nombre if producto.subcategoria_id else "",
            producto.linea.nombre if producto.linea_id else "",
            producto.clase.nombre if producto.clase_id else "",
            producto.marca.nombre if producto.marca_id else "",
            producto.proveedor.display_name if producto.proveedor_id else "",
            producto.codigo_proveedor or "",
            producto.unidad_medida.nombre if producto.unidad_medida_id else "",
            producto.get_tipo_iva_display(),
            float(producto.tasa_iva),
            "Sí" if producto.aplica_ieps else "No",
            float(producto.tasa_ieps) if producto.tasa_ieps is not None else None,
            producto.get_costeo_display(),
            float(producto.precio_costo),
            float(producto.precio_venta),
            *[
                (float(getattr(producto, campo)) if getattr(producto, campo) is not None else None)
                for _, campo in LISTAS_PRECIO_TABLA
            ],
            float(producto.stock_minimo),
            float(producto.stock_maximo),
            float(producto.peso) if producto.peso is not None else None,
            producto.dias_reserva,
        ])

    for indice, _ in enumerate(ENCABEZADOS, start=1):
        hoja.column_dimensions[hoja.cell(row=1, column=indice).column_letter].width = 18

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    fecha = timezone.localdate().isoformat()
    response["Content-Disposition"] = f'attachment; filename="productos_{fecha}.xlsx"'
    workbook.save(response)
    return response
