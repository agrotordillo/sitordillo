# python imports
import random
import string
import uuid
# django imports
from django.db import IntegrityError
from django.db import models
from django.conf import settings
from django.utils.text import slugify


class BaseAbstractModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    folio = models.CharField(max_length=20, unique=True, editable=False)
    slug = models.SlugField(max_length=255, unique=True, editable=False)
    is_active = models.BooleanField(default=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
        null=True,
        blank=True
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
        null=True,
        blank=True
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def get_folio_prefix(self):
        return "SYS"

    def get_slug_source(self):
        return str(self.uuid)

    def _generate_unique_folio(self):
        prefix = self.get_folio_prefix()
        characters = string.ascii_uppercase + string.digits
        while True:
            random_part = "".join(random.choices(characters, k=8))
            new_folio = f"{prefix}-{random_part}"
            if not self.__class__.objects.filter(folio=new_folio).exists():
                return new_folio

    def _generate_unique_slug(self):
        source = self.get_slug_source() or str(self.uuid)
        base_slug = slugify(source) or str(self.uuid)
        slug = base_slug
        counter = 2
        while self.__class__.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.folio:
            self.folio = self._generate_unique_folio()

        if not self.slug:
            self.slug = self._generate_unique_slug()

        for _ in range(3):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError:
                # Rare concurrent collision: regenerate identifiers and retry.
                self.folio = self._generate_unique_folio()
                self.slug = self._generate_unique_slug()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.__class__.__name__} ({self.folio})"