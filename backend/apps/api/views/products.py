from django.db.models import Q
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
    donde renderizar todas las opciones no es viable."""
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response([])

        productos = (
            Producto.objects.filter(is_active=True)
            .filter(
                Q(folio__icontains=q)
                | Q(sku__icontains=q)
                | Q(codigo_barras__icontains=q)
                | Q(nombre__icontains=q)
            )
            .order_by("nombre")[:20]
        )
        data = [
            {
                "id": p.id,
                "folio": p.folio,
                "sku": p.sku,
                "nombre": p.nombre,
                "precio_venta": str(p.precio_venta),
            }
            for p in productos
        ]
        return Response(data)


class UnitMeasureQuickCreateView(APIView):
    """Alta rápida de Unidad de medida desde el formulario de producto."""
    permission_classes = [AllowAny]

    def post(self, request):
        form = UnitMeasureForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=400)
        obj = form.save()
        return Response({"value": obj.id, "label": str(obj)}, status=201)
