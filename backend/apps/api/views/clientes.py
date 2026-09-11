from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clientes.models import Cliente


class ClienteBuscarView(APIView):
    """Busca clientes por folio, RFC o nombre. Reemplaza el <select> con el
    catálogo completo de clientes en cotizaciones y ventas de mostrador. Sin
    permission_classes propio: usa el default del proyecto (IsAuthenticated)."""

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response([])

        clientes = (
            Cliente.objects.filter(is_active=True)
            .filter(Q(folio__icontains=q) | Q(rfc__icontains=q) | Q(nombre__icontains=q))
            .order_by("nombre")[:20]
        )
        data = [
            {
                "id": c.id,
                "folio": c.folio,
                "rfc": c.rfc,
                "nombre": c.display_name,
            }
            for c in clientes
        ]
        return Response(data)
