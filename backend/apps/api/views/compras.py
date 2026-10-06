from rest_framework.response import Response
from rest_framework.views import APIView

from apps.compras.models import PromocionProveedor
from apps.core.parametros import fecha as leer_fecha, id_valido
from apps.products.models import Producto


class PromocionVigenteView(APIView):
    """Consulta si hay una promoción vigente de un proveedor sobre un producto
    en una fecha dada, usada para sugerir el precio en la Orden de Compra."""

    def get(self, request):
        producto_id = id_valido(request.query_params.get("producto"))
        proveedor_id = id_valido(request.query_params.get("proveedor"))
        fecha = leer_fecha(str(request.query_params.get("fecha") or "")[:10])
        if not (producto_id and proveedor_id and fecha):
            return Response({"vigente": False})

        promo = (
            PromocionProveedor.objects.filter(
                producto_id=producto_id,
                proveedor_id=proveedor_id,
                is_active=True,
                fecha_inicio__lte=fecha,
                fecha_fin__gte=fecha,
            )
            .order_by("-fecha_inicio")
            .first()
        )
        if not promo:
            return Response({"vigente": False})

        producto = Producto.objects.filter(pk=producto_id).first()
        if not producto:
            return Response({"vigente": False})

        precio_sugerido = promo.precio_para(producto.precio_costo)
        return Response({
            "vigente": True,
            "tipo": promo.tipo_descuento,
            "precio_sugerido": str(precio_sugerido),
        })
