from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import EnvioUnico


class Command(BaseCommand):
    help = (
        "Borra los tokens de envío único (apps.core.envio_unico) más viejos que --dias. "
        "Solo protegen contra un reenvío del mismo formulario, que ocurre en segundos o "
        "minutos: después ya no sirven. Pensado para correr a diario (cron)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=7, help="Antigüedad mínima a borrar (default: 7).")
        parser.add_argument("--lote", type=int, default=5000, help="Filas por DELETE (default: 5000).")

    def handle(self, *args, dias, lote, **options):
        limite = timezone.now() - timedelta(days=max(dias, 1))
        total = 0
        # Por lotes: un DELETE enorme bloquearía la tabla mientras se
        # registran ventas o pagos.
        while True:
            tokens = list(EnvioUnico.objects.filter(creado__lt=limite).values_list("pk", flat=True)[:lote])
            if not tokens:
                break
            total += EnvioUnico.objects.filter(pk__in=tokens).delete()[0]
        self.stdout.write(self.style.SUCCESS(f"Tokens de envío borrados: {total}"))
