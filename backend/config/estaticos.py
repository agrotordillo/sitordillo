from django.contrib.staticfiles.apps import StaticFilesConfig


class EstaticosConfig(StaticFilesConfig):
    """django.contrib.staticfiles, sin publicar la fuente de Tailwind.

    static/src/input.css solo es la entrada de `npm run build:css` (se
    compila a output.css). Con el almacenamiento con manifiesto de
    producción (B26 en docs/AUDITORIA.md), collectstatic falla al intentar
    resolver su `@import "tailwindcss"` como si fuera un archivo, y de todos
    modos no tiene por qué servirse. El patrón lleva `*` porque se compara
    contra la ruta relativa, que en Windows usa `\\`."""

    ignore_patterns = [*StaticFilesConfig.ignore_patterns, "*input.css"]
