from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory

from apps.core.archivos import ComprobanteFormMixin
from apps.core.forms import BaseModelForm
from apps.core.scoping import almacenes_visibles
from apps.products.models import Almacen, PuntoVenta, Turno
from apps.proveedores.models import Proveedor
from .models import CentroCosto, ConceptoGasto, Gasto, GastoDistribucion, GrupoGasto, Vehiculo


def conceptos_agrupados(queryset):
    """Opciones del select de concepto de gasto agrupadas por su grupo
    (<optgroup>), para no tener que buscar entre más de cien conceptos en
    una sola lista."""
    opciones = [("", "---------")]
    grupo_actual, bloque = None, []
    for concepto in queryset.select_related("grupo").order_by("grupo__orden", "grupo__nombre", "nombre"):
        if concepto.grupo != grupo_actual:
            if bloque:
                opciones.append((grupo_actual.nombre, bloque))
            grupo_actual, bloque = concepto.grupo, []
        bloque.append((concepto.pk, concepto.nombre))
    if bloque:
        opciones.append((grupo_actual.nombre, bloque))
    return opciones


class CentroCostoForm(BaseModelForm):
    class Meta:
        model = CentroCosto
        fields = ["codigo", "nombre", "tipo", "almacen", "descripcion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["almacen"].queryset = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        self.fields["almacen"].required = False
        self.fields["codigo"].required = False
        self.fields["descripcion"].required = False


class ConceptoGastoForm(BaseModelForm):
    class Meta:
        model = ConceptoGasto
        fields = ["grupo", "nombre", "cuenta_contable", "naturaleza", "descripcion", "ejemplos", "criterio"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 2}),
            "ejemplos": forms.Textarea(attrs={"rows": 2}),
            "criterio": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo"].queryset = GrupoGasto.objects.filter(is_active=True)
        for campo in ("cuenta_contable", "descripcion", "ejemplos", "criterio"):
            self.fields[campo].required = False


class VehiculoForm(BaseModelForm):
    class Meta:
        model = Vehiculo
        fields = ["nombre", "tipo", "placas", "centro_costo", "responsable", "descripcion"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["centro_costo"].queryset = CentroCosto.objects.filter(is_active=True)
        for campo in ("placas", "centro_costo", "responsable", "descripcion"):
            self.fields[campo].required = False


class GastoForm(ComprobanteFormMixin, BaseModelForm):
    class Meta:
        model = Gasto
        fields = [
            "centro_costo", "concepto_gasto", "vehiculo", "proveedor", "turno", "descripcion", "referencia", "condicion",
            "responsable", "fecha", "importe", "facturado", "referencia_factura", "comprobante",
            "es_compartido", "observaciones",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Al editar, cada select conserva el valor que el gasto ya tenía
        # aunque hoy no sea elegible (turno ya cerrado, concepto, unidad o
        # centro desactivado): la factura o el reembolso de un gasto llegan
        # semanas después de que se cerró su turno, y sin esto el gasto ya
        # no se podría guardar. `Q(pk=None)` no coincide con nada, así que
        # en un alta solo quedan las opciones vigentes.
        actual = self.instance
        centros_costo = CentroCosto.objects.filter(Q(is_active=True) | Q(pk=actual.centro_costo_id))
        # Solo turnos de caja: el gasto se paga con el dinero de una caja,
        # un turno de mostrador (punto de venta tipo Pedido) no maneja
        # dinero.
        turnos = Turno.objects.filter(
            Q(estatus=Turno.Estatus.ABIERTO, punto_venta__tipo=PuntoVenta.Tipo.COBRO) | Q(pk=actual.turno_id)
        ).select_related("punto_venta__almacen")
        # El origen del gasto (quién lo paga) sí queda acotado a la
        # sucursal del usuario restringido; a diferencia del destino de
        # una distribución (GastoDistribucionForm), que necesita poder
        # abarcar sucursales que no son la suya.
        if user is not None:
            visibles = almacenes_visibles(user)
            if visibles is not None:
                centros_costo = centros_costo.filter(almacen__in=visibles)
                turnos = turnos.filter(punto_venta__almacen__in=visibles)
        self.fields["centro_costo"].queryset = centros_costo
        conceptos = ConceptoGasto.objects.filter(Q(is_active=True) | Q(pk=actual.concepto_gasto_id))
        self.fields["concepto_gasto"].queryset = conceptos
        self.fields["concepto_gasto"].choices = conceptos_agrupados(conceptos)
        self.fields["vehiculo"].queryset = Vehiculo.objects.filter(Q(is_active=True) | Q(pk=actual.vehiculo_id))
        self.fields["vehiculo"].required = False
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)
        self.fields["proveedor"].required = False
        # Turno es obligatorio solo cuando el centro de costo es de tipo
        # Sucursal (ver Gasto.clean()); a nivel de formulario se deja
        # opcional para no bloquear los demás tipos de centro de costo.
        self.fields["turno"].queryset = turnos
        self.fields["turno"].required = False
        self.fields["referencia"].required = False
        self.fields["responsable"].required = False
        self.fields["referencia_factura"].required = False
        self.fields["comprobante"].required = False
        self.fields["observaciones"].required = False


class GastoDistribucionForm(BaseModelForm):
    class Meta:
        model = GastoDistribucion
        fields = ["centro_costo", "monto"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cualquier tipo de centro de costo puede recibir parte de un gasto
        # compartido (p. ej. una factura de gasolina repartida entre
        # Transportes, Administración y Gasto personal).
        self.fields["centro_costo"].queryset = CentroCosto.objects.filter(is_active=True)
        self.fields["monto"].widget.attrs.update({
            "class": (self.fields["monto"].widget.attrs.get("class", "") + " fs-monto").strip(),
            "step": "0.01",
            "min": "0.01",
        })


GastoDistribucionFormSet = inlineformset_factory(
    Gasto,
    GastoDistribucion,
    form=GastoDistribucionForm,
    extra=1,
    can_delete=True,
)
