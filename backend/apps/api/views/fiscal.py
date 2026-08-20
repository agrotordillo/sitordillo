from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fiscal.models import ClaveProdServSAT, ClaveUnidadSAT


class ClaveProdServBuscarView(APIView):
    """Busca en el catálogo local de claves de producto/servicio SAT (ya
    sembrado con el catálogo oficial CFDI 4.0, ~52 mil registros). Pensado
    para reemplazar un <select> gigante, que era la causa de que el
    formulario de producto tardara mucho en cargar al editar."""
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 3:
            return Response([])

        claves = (
            ClaveProdServSAT.objects.filter(is_active=True)
            .filter(Q(clave__icontains=q) | Q(descripcion__icontains=q))
            .order_by("clave")[:20]
        )
        data = [{"id": c.id, "clave": c.clave, "descripcion": c.descripcion} for c in claves]
        return Response(data)


class ClaveUnidadBuscarView(APIView):
    """Busca en el catálogo local de claves de unidad SAT (~2,400 registros)."""
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 3:
            return Response([])

        claves = (
            ClaveUnidadSAT.objects.filter(is_active=True)
            .filter(Q(clave__icontains=q) | Q(nombre__icontains=q))
            .order_by("clave")[:20]
        )
        data = [{"id": c.id, "clave": c.clave, "nombre": c.nombre} for c in claves]
        return Response(data)
