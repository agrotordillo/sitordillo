from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction

from apps.core.archivos import RutaAleatoria
from apps.core.models import BaseAbstractModel


class CentroCosto(BaseAbstractModel):
    """A dónde se le carga un gasto. Generaliza a `products.Almacen`: una
    sucursal de venta es un centro de costo (ligado a su Almacen, para poder
    cruzar su gasto contra `ventas.Venta` y calcular el punto de equilibrio),
    pero también existen centros que no venden y aun así deben llevar su
    propio control de gasto -por ejemplo, para la declaración fiscal del
    PFAE que agrupa todas las actividades del negocio- como proyectos
    agropecuarios, administración corporativa o gasto personal de los
    dueños. Las unidades de negocio (renta de mobiliario, transportes,
    arrendamiento de inmuebles) sí tienen ingreso propio, pero no venden
    en mostrador ni tienen almacén."""

    class Tipo(models.TextChoices):
        SUCURSAL = "sucursal", "Sucursal (venta al público)"
        UNIDAD_NEGOCIO = "unidad_negocio", "Unidad de negocio (ingreso propio, sin mostrador)"
        PROYECTO = "proyecto", "Proyecto / actividad no comercial"
        ADMINISTRATIVO = "administrativo", "Administración / corporativo"
        PERSONAL = "personal", "Gasto personal de los dueños"

    codigo = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Código corto",
        help_text="Identificador corto para reconocerlo rápido en reportes (p. ej. \"01\" o \"SUR\"). Opcional.",
    )
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Nombre")
    tipo = models.CharField(max_length=15, choices=Tipo.choices, verbose_name="Tipo de centro de costo")
    almacen = models.OneToOneField(
        "products.Almacen",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="centro_costo",
        verbose_name="Sucursal (almacén)",
        help_text="Obligatorio y único para centros de tipo Sucursal; no aplica a los demás tipos.",
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Centro de costo"
        verbose_name_plural = "Centros de costo"
        ordering = ["codigo", "nombre"]
        indexes = [
            models.Index(fields=["tipo"]),
        ]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}" if self.codigo else self.nombre

    def get_folio_prefix(self):
        return "CCO"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.codigo == "":
            self.codigo = None
        if self.tipo == self.Tipo.SUCURSAL:
            if not self.almacen_id:
                raise ValidationError({"almacen": "Un centro de costo de tipo Sucursal debe ligarse a un almacén."})
            if self.almacen.tipo != self.almacen.Tipo.SUCURSAL:
                raise ValidationError({"almacen": "El almacén ligado debe ser de tipo Sucursal, no CEDIS."})
        elif self.almacen_id:
            raise ValidationError({"almacen": "Solo los centros de tipo Sucursal se ligan a un almacén."})


class GrupoGasto(BaseAbstractModel):
    """Agrupador de conceptos de gasto (Nómina, Servicios, Mantenimiento,
    Activo fijo...). Su `clasificacion` decide si lo registrado con sus
    conceptos es gasto de operación o no: la compra de un activo fijo o un
    retiro de la propietaria se capturan en el mismo módulo para no perder
    su rastro, pero no deben inflar el gasto del punto de equilibrio."""

    class Clasificacion(models.TextChoices):
        GASTO = "gasto", "Gasto de operación"
        INVERSION = "inversion", "Inversión / activo fijo"
        NO_OPERATIVO = "no_operativo", "Movimiento no operativo"

    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre del grupo",
        error_messages={"unique": "Ya existe un %(model_name)s con este nombre."},
    )
    clasificacion = models.CharField(
        max_length=15,
        choices=Clasificacion.choices,
        default=Clasificacion.GASTO,
        verbose_name="Clasificación",
        help_text="Solo lo clasificado como Gasto de operación cuenta en el reporte de punto de equilibrio.",
    )
    orden = models.PositiveSmallIntegerField(default=0, verbose_name="Orden")
    exclusivo_personal = models.BooleanField(
        default=False,
        verbose_name="Solo para centros de costo de tipo Personal",
        help_text="Sus conceptos (p. ej. gastos médicos o colegiaturas de los dueños) no se pueden cargar a una "
        "sucursal, proyecto o unidad de negocio.",
    )

    class Meta:
        verbose_name = "Grupo de gasto"
        verbose_name_plural = "Grupos de gasto"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "GRG"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()

    @property
    def cuenta_en_resultados(self):
        return self.clasificacion == self.Clasificacion.GASTO


class ConceptoGasto(BaseAbstractModel):
    """Concepto de gasto: el nivel en el que se clasifica cada gasto
    capturado (Agua, Mantenimiento eléctrico, Peajes de caseta...). Viene
    del catálogo con guía contabilizadora que definió el negocio; cada
    concepto guarda la cuenta del plan de cuentas contable a la que se
    envía (varios conceptos pueden compartir cuenta) y la guía de qué sí y
    qué no se registra en él, para mostrarla al capturar. Es catálogo de
    contabilidad: lo mantiene el Administrador, quien captura solo lo usa."""

    class Naturaleza(models.TextChoices):
        FIJO = "fijo", "Fijo"
        VARIABLE = "variable", "Variable"

    grupo = models.ForeignKey(
        GrupoGasto,
        on_delete=models.PROTECT,
        related_name="conceptos",
        verbose_name="Grupo",
    )
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre del concepto",
        error_messages={"unique": "Ya existe un concepto de gasto con este nombre."},
    )
    cuenta_contable = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Cuenta contable",
        help_text="Cuenta del plan de cuentas contable (p. ej. 4101-015-000) a la que se envía este concepto.",
    )
    naturaleza = models.CharField(
        max_length=10,
        choices=Naturaleza.choices,
        default=Naturaleza.VARIABLE,
        verbose_name="Naturaleza",
        help_text="Fijo: no depende de cuánto se venda (renta, internet). Variable: depende del nivel de operación.",
    )
    descripcion = models.TextField(blank=True, verbose_name="Qué debe registrarse")
    ejemplos = models.TextField(blank=True, verbose_name="Ejemplos de captura")
    criterio = models.TextField(blank=True, verbose_name="Criterio / no incluir")

    class Meta:
        verbose_name = "Concepto de gasto"
        verbose_name_plural = "Conceptos de gasto"
        ordering = ["grupo__orden", "nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "CAT"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()

    def admite_centro(self, centro_costo):
        """Un concepto de un grupo exclusivo de gasto personal solo se carga
        a centros de tipo Personal (ver GrupoGasto.exclusivo_personal): así
        un gasto médico de los dueños no termina en el punto de equilibrio
        de una sucursal."""
        return not self.grupo.exclusivo_personal or centro_costo.tipo == CentroCosto.Tipo.PERSONAL


def mensaje_solo_personal(concepto):
    return (
        f"«{concepto.nombre}» es un gasto personal de los dueños: solo se carga a un centro de costo de tipo "
        "Personal."
    )


class Vehiculo(BaseAbstractModel):
    """Unidad (vehículo o maquinaria) a la que se le liga un gasto de
    combustible, casetas, rastreo, refacciones o mantenimiento, para poder
    saber cuánto cuesta operar cada una. Es opcional en el gasto: una carga
    de gasolina de un auto particular, por ejemplo, no tiene unidad."""

    class Tipo(models.TextChoices):
        VEHICULO = "vehiculo", "Vehículo"
        MAQUINARIA = "maquinaria", "Maquinaria / equipo"

    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre",
        help_text="Cómo se le conoce en la operación (p. ej. \"Nissan 2014\", \"KW 2017\", \"Montacargas\").",
        error_messages={"unique": "Ya existe una unidad con este nombre."},
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, verbose_name="Tipo")
    placas = models.CharField(max_length=15, blank=True, verbose_name="Placas")
    centro_costo = models.ForeignKey(
        CentroCosto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vehiculos",
        verbose_name="Centro de costo habitual",
        help_text="A dónde se carga normalmente su gasto. Es solo una referencia: cada gasto elige su centro.",
    )
    responsable = models.CharField(max_length=150, blank=True, verbose_name="Responsable / chofer")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Vehículo o maquinaria"
        verbose_name_plural = "Vehículos y maquinaria"
        ordering = ["tipo", "nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "VEH"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class Gasto(BaseAbstractModel):
    """Un gasto registrado contra un centro de costo. Cuando `es_compartido`
    es verdadero, el importe no se contabiliza directamente al centro de
    costo de origen: se reparte entre los centros beneficiados (sucursales,
    unidades de negocio, proyectos...) mediante `GastoDistribucion`, con
    montos exactos capturados a mano (nunca un promedio automático), porque
    el consumo real de cada uno no es proporcional -por ejemplo, el reparto
    de agua depende de cuánto personal tiene cada sucursal, y el de una
    factura de gasolina, de qué unidad cargó cuánto."""

    class Condicion(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADO = "pagado", "Pagado"
        CANCELADO = "cancelado", "Cancelado"

    numero = models.PositiveIntegerField(unique=True, editable=False, verbose_name="Número")
    centro_costo = models.ForeignKey(
        CentroCosto,
        on_delete=models.PROTECT,
        related_name="gastos",
        verbose_name="Centro de costo de origen",
        help_text="Quién generó/pagó el gasto. Si es compartido, aquí se registra el centro de origen (p. ej. "
        "Administración) y el detalle real por centro de costo va en la distribución.",
    )
    concepto_gasto = models.ForeignKey(
        ConceptoGasto,
        on_delete=models.PROTECT,
        related_name="gastos",
        verbose_name="Concepto de gasto",
    )
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gastos",
        verbose_name="Vehículo o maquinaria",
        help_text="Opcional: la unidad a la que corresponde el gasto (combustible, casetas, refacciones, mantenimiento).",
    )
    proveedor = models.ForeignKey(
        "proveedores.Proveedor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gastos",
        verbose_name="Proveedor",
    )
    turno = models.ForeignKey(
        "products.Turno",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gastos",
        verbose_name="Turno",
        help_text="Obligatorio cuando el centro de costo es de tipo Sucursal: el turno abierto de esa sucursal en "
        "el que se aplicó el gasto.",
    )
    descripcion = models.CharField(
        max_length=255,
        verbose_name="Descripción del gasto",
        help_text="Lo que dice el vale (p. ej. \"Pago de recibo de luz de Lerdo, bimestre 4\").",
    )
    referencia = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referencia",
        help_text="Referencia interna/administrativa (folio de caja, número de memo, clave de control propia). "
        "No es el folio o UUID fiscal -para eso está \"Referencia de factura\".",
    )
    condicion = models.CharField(
        max_length=10,
        choices=Condicion.choices,
        default=Condicion.PENDIENTE,
        verbose_name="Condición",
        help_text="Estado de seguimiento del gasto, independiente de si está facturado. Un gasto Cancelado no "
        "cuenta en el reporte de punto de equilibrio.",
    )
    responsable = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Responsable",
        help_text="Quién recibió o autorizó el gasto (nombre libre; no necesariamente un usuario del sistema).",
    )
    fecha = models.DateField(verbose_name="Fecha del gasto")
    importe = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Importe total")
    facturado = models.BooleanField(default=False, verbose_name="Facturado (con CFDI)")
    referencia_factura = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Referencia de factura",
        help_text="Folio o UUID fiscal, cuando el gasto está facturado.",
    )
    comprobante = models.FileField(
        upload_to=RutaAleatoria("gastos/comprobantes"),
        null=True,
        blank=True,
        verbose_name="Comprobante",
    )
    es_compartido = models.BooleanField(
        default=False,
        verbose_name="Se distribuye entre varios centros de costo",
        help_text="Actívalo cuando el gasto beneficia a más de un centro de costo (p. ej. una factura de gasolina "
        "que se reparte entre Transporte, Administración y Personal) y necesites repartirlo con montos exactos.",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ["-fecha", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(importe__gt=0), name="gto_importe_positivo"),
        ]
        indexes = [
            models.Index(fields=["centro_costo"]),
            models.Index(fields=["concepto_gasto"]),
            models.Index(fields=["fecha"]),
            models.Index(fields=["turno"]),
            models.Index(fields=["condicion"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.descripcion}"

    def get_folio_prefix(self):
        return "GTO"

    def get_slug_source(self):
        return f"{self.folio}-{self.centro_costo_id}"

    def _guardar_con_numero_nuevo(self, *args, **kwargs):
        with transaction.atomic():
            ultimo = Gasto.objects.select_for_update().order_by("-numero").first()
            self.numero = (ultimo.numero if ultimo else 0) + 1
            super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.numero is not None:
            super().save(*args, **kwargs)
            return
        for _ in range(3):
            try:
                self._guardar_con_numero_nuevo(*args, **kwargs)
                return
            except IntegrityError:
                self.numero = None
        self._guardar_con_numero_nuevo(*args, **kwargs)

    @property
    def display_name(self):
        return self.__str__()

    @property
    def monto_distribuido(self):
        return sum((d.monto for d in self.distribuciones.all()), Decimal("0.00"))

    @property
    def distribucion_cuadra(self):
        if not self.es_compartido:
            return True
        return self.monto_distribuido == self.importe

    def clean(self):
        super().clean()
        if self.importe is not None and self.importe <= 0:
            raise ValidationError({"importe": "El importe debe ser mayor a cero."})
        if self.facturado and not self.referencia_factura:
            raise ValidationError({"referencia_factura": "Indica el folio o UUID fiscal de la factura."})
        if not self.facturado and self.referencia_factura:
            raise ValidationError({"referencia_factura": "Solo aplica cuando el gasto está facturado."})
        if self.centro_costo_id and self.centro_costo.tipo == CentroCosto.Tipo.SUCURSAL:
            if not self.turno_id:
                raise ValidationError({"turno": "Indica el turno de la sucursal en el que se aplicó el gasto."})
            if self.turno.punto_venta.almacen_id != self.centro_costo.almacen_id:
                raise ValidationError({"turno": "El turno elegido no corresponde a la sucursal de este gasto."})
        elif self.turno_id:
            raise ValidationError({"turno": "Solo aplica cuando el centro de costo es de tipo Sucursal."})
        # Si es compartido, el centro de origen solo es quien pagó: el cargo
        # real va en la distribución, que se valida aparte
        # (services.validar_centros_del_concepto).
        if (
            self.concepto_gasto_id and self.centro_costo_id and not self.es_compartido
            and not self.concepto_gasto.admite_centro(self.centro_costo)
        ):
            raise ValidationError({"centro_costo": mensaje_solo_personal(self.concepto_gasto)})


class GastoDistribucion(BaseAbstractModel):
    """Monto exacto de un gasto compartido que le corresponde a un centro
    de costo (de cualquier tipo, no solo sucursal). La suma de todas las distribuciones de un mismo `Gasto` debe
    ser exactamente igual a `Gasto.importe` (se valida al guardar, no es un
    promedio calculado)."""

    gasto = models.ForeignKey(
        Gasto,
        on_delete=models.CASCADE,
        related_name="distribuciones",
        verbose_name="Gasto",
    )
    centro_costo = models.ForeignKey(
        CentroCosto,
        on_delete=models.PROTECT,
        related_name="distribuciones_gasto",
        verbose_name="Centro de costo beneficiado",
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto asignado")

    class Meta:
        verbose_name = "Distribución de gasto"
        verbose_name_plural = "Distribuciones de gasto"
        constraints = [
            models.CheckConstraint(condition=models.Q(monto__gt=0), name="gtd_monto_positivo"),
            models.UniqueConstraint(fields=["gasto", "centro_costo"], name="gtd_unico_por_gasto_y_centro"),
        ]
        indexes = [
            models.Index(fields=["gasto"]),
            models.Index(fields=["centro_costo"]),
        ]

    def __str__(self):
        return f"{self.centro_costo.nombre} · ${self.monto}"

    def get_folio_prefix(self):
        return "GTD"

    def get_slug_source(self):
        return f"{self.gasto_id}-{self.centro_costo_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.monto is not None and self.monto <= 0:
            raise ValidationError({"monto": "El monto asignado debe ser mayor a cero."})


class BitacoraAccesoGastos(models.Model):
    """Quién dio o quitó una capacidad de Gastos, a quién y cuándo. Gastos
    es un módulo confidencial: ni el Administrador entra sin la capacidad
    asignada, y solo puede asignarla quien ya la tiene (ver
    apps.core.permissions), así que cada cambio queda registrado. No
    hereda de BaseAbstractModel porque es un registro histórico, no un
    catálogo: no se edita ni se desactiva."""

    class Accion(models.TextChoices):
        OTORGADA = "otorgada", "Otorgada"
        RETIRADA = "retirada", "Retirada"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bitacora_acceso_gastos",
        verbose_name="Usuario",
    )
    grupo = models.ForeignKey(
        "auth.Group",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name="Capacidad",
    )
    grupo_nombre = models.CharField(
        max_length=150,
        verbose_name="Nombre de la capacidad",
        help_text="Copia del nombre al momento del cambio, por si el grupo se renombra o se borra.",
    )
    accion = models.CharField(max_length=10, choices=Accion.choices, verbose_name="Acción")
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Realizado por",
        help_text="Vacío cuando el cambio se hizo desde el servidor (migración o comando), no desde el sistema.",
    )
    nota = models.CharField(max_length=255, blank=True, verbose_name="Nota")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        verbose_name = "Registro de acceso a Gastos"
        verbose_name_plural = "Bitácora de acceso a Gastos"
        ordering = ["-fecha", "-pk"]
        indexes = [
            models.Index(fields=["usuario"]),
            models.Index(fields=["fecha"]),
        ]

    def __str__(self):
        return f"{self.get_accion_display()} {self.grupo_nombre} a {self.usuario}"

    @classmethod
    def registrar_cambios(cls, usuario, antes, despues, realizado_por=None, nota=""):
        """Registra la diferencia entre las capacidades protegidas que
        `usuario` tenía (`antes`) y las que quedó teniendo (`despues`)."""
        antes, despues = set(antes), set(despues)
        cls.objects.bulk_create(
            [
                cls(usuario=usuario, grupo=grupo, grupo_nombre=grupo.name, accion=accion,
                    realizado_por=realizado_por, nota=nota)
                for accion, grupos in ((cls.Accion.OTORGADA, despues - antes), (cls.Accion.RETIRADA, antes - despues))
                for grupo in sorted(grupos, key=lambda g: g.name)
            ]
        )
