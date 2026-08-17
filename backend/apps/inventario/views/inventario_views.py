from django.db.models import Sum
from django.views.generic import ListView

from apps.inventario.models import Lote


class LoteListView(ListView):
    model = Lote
    template_name = "inventario/lote_list.html"
    context_object_name = "lotes"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(cantidad_disponible__gt=0)
            .select_related("producto", "almacen")
            .order_by("fecha_caducidad", "fecha_ingreso")
        )


class ExistenciaListView(ListView):
    template_name = "inventario/existencia_list.html"
    context_object_name = "existencias"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        return (
            Lote.objects.filter(is_active=True, cantidad_disponible__gt=0)
            .values("producto__nombre", "producto__sku", "almacen__nombre")
            .annotate(total=Sum("cantidad_disponible"))
            .order_by("producto__nombre", "almacen__nombre")
        )
