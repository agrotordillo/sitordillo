from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.forms import BrandForm, SupplierForm, UnitMeasureForm
from apps.products.models import Subcategoria
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


class SupplierQuickCreateView(APIView):
    """Alta rápida de Proveedor desde el formulario de producto."""
    permission_classes = [AllowAny]

    def post(self, request):
        form = SupplierForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=400)
        obj = form.save()
        return Response({"value": obj.id, "label": obj.nombre}, status=201)


class UnitMeasureQuickCreateView(APIView):
    """Alta rápida de Unidad de medida desde el formulario de producto."""
    permission_classes = [AllowAny]

    def post(self, request):
        form = UnitMeasureForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=400)
        obj = form.save()
        return Response({"value": obj.id, "label": str(obj)}, status=201)
