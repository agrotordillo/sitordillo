from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class RegimenFiscal(BaseAbstractModel):
    clave = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Clave SAT",
        error_messages={"unique": "Ya existe un %(model_name)s con esta clave."},
    )
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    aplica_fisica = models.BooleanField(default=False, verbose_name="Aplica a persona física")
    aplica_moral = models.BooleanField(default=False, verbose_name="Aplica a persona moral")

    class Meta:
        verbose_name = "Régimen fiscal"
        verbose_name_plural = "Regímenes fiscales"
        ordering = ["clave"]
        indexes = [
            models.Index(fields=["clave"]),
        ]

    def __str__(self):
        return f"{self.clave} - {self.descripcion}"

    def get_folio_prefix(self):
        return "RFI"

    def get_slug_source(self):
        return f"{self.clave}-{self.descripcion}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if not self.aplica_fisica and not self.aplica_moral:
            raise ValidationError(
                "El régimen fiscal debe aplicar al menos a persona física o persona moral."
            )


class UsoCFDI(BaseAbstractModel):
    clave = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Clave SAT",
        error_messages={"unique": "Ya existe un %(model_name)s con esta clave."},
    )
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    aplica_fisica = models.BooleanField(default=False, verbose_name="Aplica a persona física")
    aplica_moral = models.BooleanField(default=False, verbose_name="Aplica a persona moral")

    class Meta:
        verbose_name = "Uso CFDI"
        verbose_name_plural = "Usos CFDI"
        ordering = ["clave"]
        indexes = [
            models.Index(fields=["clave"]),
        ]

    def __str__(self):
        return f"{self.clave} - {self.descripcion}"

    def get_folio_prefix(self):
        return "UCF"

    def get_slug_source(self):
        return f"{self.clave}-{self.descripcion}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if not self.aplica_fisica and not self.aplica_moral:
            raise ValidationError(
                "El uso CFDI debe aplicar al menos a persona física o persona moral."
            )


class FormaPago(BaseAbstractModel):
    clave = models.CharField(
        max_length=5,
        unique=True,
        verbose_name="Clave SAT",
        error_messages={"unique": "Ya existe un %(model_name)s con esta clave."},
    )
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")

    class Meta:
        verbose_name = "Forma de pago"
        verbose_name_plural = "Formas de pago"
        ordering = ["clave"]
        indexes = [
            models.Index(fields=["clave"]),
        ]

    def __str__(self):
        return f"{self.clave} - {self.descripcion}"

    def get_folio_prefix(self):
        return "FPG"

    def get_slug_source(self):
        return f"{self.clave}-{self.descripcion}"

    @property
    def display_name(self):
        return self.__str__()


class MetodoPago(BaseAbstractModel):
    clave = models.CharField(
        max_length=5,
        unique=True,
        verbose_name="Clave SAT",
        error_messages={"unique": "Ya existe un %(model_name)s con esta clave."},
    )
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")

    class Meta:
        verbose_name = "Método de pago"
        verbose_name_plural = "Métodos de pago"
        ordering = ["clave"]
        indexes = [
            models.Index(fields=["clave"]),
        ]

    def __str__(self):
        return f"{self.clave} - {self.descripcion}"

    def get_folio_prefix(self):
        return "MPG"

    def get_slug_source(self):
        return f"{self.clave}-{self.descripcion}"

    @property
    def display_name(self):
        return self.__str__()


class ClaveUnidadSAT(BaseAbstractModel):
    clave = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Clave SAT",
        error_messages={"unique": "Ya existe un %(model_name)s con esta clave."},
    )
    nombre = models.CharField(max_length=255, verbose_name="Nombre de la unidad")
    simbolo = models.CharField(max_length=20, blank=True, verbose_name="Símbolo")

    class Meta:
        verbose_name = "Clave de unidad SAT"
        verbose_name_plural = "Claves de unidad SAT"
        ordering = ["clave"]
        indexes = [
            models.Index(fields=["clave"]),
        ]

    def __str__(self):
        return f"{self.clave} - {self.nombre}"

    def get_folio_prefix(self):
        return "CUS"

    def get_slug_source(self):
        return f"{self.clave}-{self.nombre}"

    @property
    def display_name(self):
        return self.__str__()


class ClaveProdServSAT(BaseAbstractModel):
    clave = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Clave SAT",
        error_messages={"unique": "Ya existe un %(model_name)s con esta clave."},
    )
    descripcion = models.TextField(verbose_name="Descripción")

    class Meta:
        verbose_name = "Clave de producto o servicio SAT"
        verbose_name_plural = "Claves de producto o servicio SAT"
        ordering = ["clave"]
        indexes = [
            models.Index(fields=["clave"]),
        ]

    def __str__(self):
        return f"{self.clave} - {self.descripcion[:60]}"

    def get_folio_prefix(self):
        return "CPS"

    def get_slug_source(self):
        return f"{self.clave}"

    @property
    def display_name(self):
        return self.__str__()
