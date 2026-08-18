from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.proveedores.models import Proveedor


class ProveedorBuscarView(APIView):
    """Busca proveedores por folio, RFC o nombre (fiscal o comercial). Pensado
    para reemplazar un <select> con el catálogo completo de proveedores, que
    ya ronda los 300 registros y sigue creciendo."""
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response([])

        proveedores = (
            Proveedor.objects.filter(is_active=True)
            .filter(
                Q(folio__icontains=q)
                | Q(rfc__icontains=q)
                | Q(nombre_fiscal__icontains=q)
                | Q(nombre_comercial__icontains=q)
            )
            .order_by("nombre_fiscal")[:20]
        )
        data = [
            {
                "id": p.id,
                "folio": p.folio,
                "rfc": p.rfc,
                "nombre": p.display_name,
            }
            for p in proveedores
        ]
        return Response(data)
