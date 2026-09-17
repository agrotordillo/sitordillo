from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.core.scoping import almacen_principal, almacenes_visibles
from apps.clientes.models import Cliente
from apps.fiscal.models import FormaPago
from apps.pagos.forms import FormaPagoSelect
from apps.products.models import Almacen, Producto
from .models import DevolucionCliente, DevolucionClienteDetalle, Venta, VentaDetalle, VentaPago


class VentaForm(BaseModelForm):
    # No es un campo de Venta: es el toggle que decide si el cobro se
    # captura con una sola forma de pago (forma_pago) o dividido en varias
    # (ver VentaPagoFormSet); VentaCreateView.form_valid() lo lee de
    # cleaned_data y decide cuál de las dos guardar -nunca ambas-.
    pago_dividido = forms.BooleanField(required=False, label="Dividir el cobro en varias formas de pago")

    class Meta:
        model = Venta
        # fecha_venta no se captura: toma el default del modelo
        # (timezone.now al momento de guardar).
        fields = [
            "cliente", "almacen", "forma_pago", "referencia_pago", "efectivo_recibido", "observaciones",
        ]
        widgets = {
            # Mismo patrón de búsqueda por texto que producto (ver
            # cliente-search.js): con el catálogo completo de clientes un
            # <select> deja de ser práctico.
            "cliente": forms.HiddenInput,
            # data-clave en cada <option> (ver FormaPagoSelect) es lo que
            # usa venta-cambio.js para saber, sin ir al servidor, cuándo
            # forma_pago es Efectivo y mostrar el campo de "recibido".
            "forma_pago": FormaPagoSelect,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # No siempre es obligatorio: si se dividió el cobro, forma_pago se
        # deja vacío a propósito (ver Venta.pago_dividido). Cuál de los dos
        # casos aplica se valida en VentaCreateView.form_valid(), no aquí.
        self.fields["forma_pago"].required = False
        # x-model en vez de un listener aparte: sincroniza el checkbox con
        # el x-data local del bloque "Forma de pago" en venta_form.html
        # (para mostrar/ocultar el select), independiente del x-data del
        # bloque "Pago dividido" -que escucha este mismo checkbox por su
        # cuenta, ver venta-pago-dividido.js-.
        self.fields["pago_dividido"].widget.attrs["x-model"] = "dividido"
        self.fields["efectivo_recibido"].widget.attrs.update({"step": "0.01", "min": "0"})
        self.fields["cliente"].queryset = Cliente.objects.filter(is_active=True)
        # Venta nueva sin cliente explícito: precarga "Público en general"
        # (lo más común en mostrador); se puede cambiar buscando otro
        # cliente con el autocomplete.
        if not self.instance.pk and "cliente" not in self.initial:
            publico = Cliente.publico_general()
            if publico is not None:
                self.initial["cliente"] = publico.pk

        almacenes = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        # Un usuario restringido a una o varias sucursales (ver
        # AsignacionSucursal) solo puede registrar la venta en una de las
        # suyas; sin restricción (Administrador/Auxiliar administrador) ve
        # todas, igual que antes.
        if user is not None:
            visibles = almacenes_visibles(user)
            if visibles is not None:
                almacenes = almacenes.filter(pk__in=visibles.values("pk"))
        self.fields["almacen"].queryset = almacenes

        # Usuario con una sucursal fija (ver AsignacionSucursal.es_principal):
        # no tiene sentido que la elija cada vez, se fija sola y el campo se
        # oculta. Sin una sucursal principal clara (Administrador, o sin
        # asignación) sigue viendo el select normal.
        fijo = almacen_principal(user) if user is not None else None
        if fijo is not None:
            self.fields["almacen"].widget = forms.HiddenInput()
            if not self.instance.pk and "almacen" not in self.initial:
                self.initial["almacen"] = fijo.pk


class VentaDetalleForm(BaseModelForm):
    """descuento, lista_precio y estrategia_salida NO son campos del
    formulario a propósito: el cajero no manipula el precio de una venta
    -a diferencia de una cotización, donde sí se negocia-. La lista de
    precios (la del cliente si tiene una propia, si no "PUBLICO") y la
    estrategia de salida (siempre FIFO en ventas) las resuelve
    VentaCreateView.form_valid() al guardar, y precio_unitario -aunque
    sigue en el formulario, porque su valor real se pinta ahí- se
    sobreescribe ahí también con el precio ya resuelto por
    ProductoBuscarView, sin confiar en lo que haya llegado en el POST."""

    class Meta:
        model = VentaDetalle
        fields = ["producto", "cantidad", "precio_unitario"]
        widgets = {
            # Con ~300 mil productos, un <select> normal es inviable: se
            # busca por texto (ver producto-search.js) y este campo solo
            # guarda el id elegido.
            "producto": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True)
        self.fields["cantidad"].widget.attrs.update({
            "class": (self.fields["cantidad"].widget.attrs.get("class", "") + " fs-cantidad").strip(),
            "step": "0.01",
            "min": "0.01",
        })
        self.fields["precio_unitario"].widget.attrs.update({
            "class": (self.fields["precio_unitario"].widget.attrs.get("class", "") + " fs-precio").strip(),
            "step": "0.01",
            "min": "0",
            "readonly": "readonly",
            "tabindex": "-1",
        })


VentaDetalleFormSet = inlineformset_factory(
    Venta,
    VentaDetalle,
    form=VentaDetalleForm,
    extra=1,
    can_delete=True,
)


class VentaPagoForm(BaseModelForm):
    class Meta:
        model = VentaPago
        fields = ["forma_pago", "monto", "referencia", "recibido"]
        widgets = {
            # Mismo widget que VentaForm.forma_pago: expone data-clave por
            # <option> para que venta-pago-dividido.js muestre "recibido"
            # solo en la fila que quedó en Efectivo.
            "forma_pago": FormaPagoSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # "Por definir" (crédito) no es una forma de pago real que se pueda
        # combinar en un cobro dividido: un pago dividido siempre es dinero
        # ya recibido de inmediato, nunca a crédito (ver
        # ventas.services.validar_venta_a_credito).
        self.fields["forma_pago"].queryset = FormaPago.objects.exclude(clave=Venta.CLAVE_CREDITO)
        self.fields["forma_pago"].widget.attrs["class"] = (
            self.fields["forma_pago"].widget.attrs.get("class", "") + " fs-forma-pago-dividido"
        ).strip()
        self.fields["monto"].widget.attrs.update({
            "class": (self.fields["monto"].widget.attrs.get("class", "") + " fs-monto-pago").strip(),
            "step": "0.01",
            "min": "0.01",
        })
        self.fields["recibido"].widget.attrs.update({
            "class": (self.fields["recibido"].widget.attrs.get("class", "") + " fs-recibido-pago").strip(),
            "step": "0.01",
            "min": "0",
        })


VentaPagoFormSet = inlineformset_factory(
    Venta,
    VentaPago,
    form=VentaPagoForm,
    extra=2,
    can_delete=True,
)


class DevolucionClienteForm(BaseModelForm):
    class Meta:
        model = DevolucionCliente
        fields = ["fecha", "motivo"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class DevolucionLineaForm(forms.Form):
    venta_detalle_id = forms.IntegerField(widget=forms.HiddenInput)
    cantidad = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    reingresa_a_inventario = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "venta_detalle_id" or isinstance(field.widget, forms.CheckboxInput):
                continue
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()


DevolucionFormSet = forms.formset_factory(DevolucionLineaForm, extra=0)
