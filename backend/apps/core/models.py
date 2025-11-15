# python imports
import uuid
import string
import random
# django imports
from django.db import models
from django.conf import settings
from django.utils.text import slugify


class BaseAbstractModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    folio = models.CharField(max_length=20, unique=True, editable=False)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
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

    def save(self, *args, **kwargs):
        if not self.folio:
            prefix = getattr(self, "get_folio_prefix", lambda: "SYS")()
            characters = string.ascii_uppercase + string.digits
            while True:
                random_part = ''.join(random.choices(characters, k=8))
                new_folio = f"{prefix}-{random_part}"
                if not self.__class__.objects.filter(folio=new_folio).exists():
                    self.folio = new_folio
                    break
        if not self.slug:
            if hasattr(self, "name"):
                value = getattr(self, "name")
            elif hasattr(self, "get_slug_source") and callable(self.get_slug_source):
                value = self.get_slug_source()
            else:
                value = str(self.uuid)
            self.slug = slugify(value)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.__class__.__name__} ({self.folio})"
