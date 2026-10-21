import uuid

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.core.archivos import MEGABYTE, validar_archivo
from apps.products import precios_masivos

SESION = "precios_masivos_revision"


class ArchivoPreciosForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx", "class": "input"}),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        validar_archivo(archivo, extensiones={".xlsx"}, max_bytes=5 * MEGABYTE)
        # Un .xlsx es un ZIP: la extensión la decide quien sube el archivo.
        archivo.seek(0)
        if not archivo.read(4).startswith(b"PK\x03\x04"):
            raise forms.ValidationError("El archivo no es una hoja de cálculo .xlsx válida.")
        archivo.seek(0)
        return archivo


@permission_required("products.change_productoprecio", raise_exception=True)
def plantilla_precios_view(request):
    libro = precios_masivos.generar_plantilla()
    respuesta = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    respuesta["Content-Disposition"] = 'attachment; filename="actualizacion_precios.xlsx"'
    libro.save(respuesta)
    return respuesta


@permission_required("products.change_productoprecio", raise_exception=True)
def precios_masivos_view(request):
    """Actualizar precios con la plantilla: 1) se sube el archivo y se
    muestra qué cambiaría (y los errores por línea) sin guardar nada; 2) si
    no hay errores, "Aplicar" guarda exactamente lo revisado, que se guardó
    en la sesión con un token para que no se aplique otra revisión ni dos
    veces la misma."""
    contexto = {"active_module": "products", "form": ArchivoPreciosForm()}
    accion = request.POST.get("accion") if request.method == "POST" else None

    if accion == "revisar":
        form = ArchivoPreciosForm(request.POST, request.FILES)
        contexto["form"] = form
        if form.is_valid():
            cambios, errores = precios_masivos.leer_archivo(
                form.cleaned_data["archivo"], puede_cambiar_costo=request.user.has_perm("products.change_producto"),
            )
            token = uuid.uuid4().hex
            if cambios and not errores:
                request.session[SESION] = {"token": token, "cambios": cambios}
            else:
                request.session.pop(SESION, None)
            contexto.update({
                "revisado": True,
                "archivo_nombre": form.cleaned_data["archivo"].name,
                "cambios": cambios,
                "errores": errores,
                "token": token,
                "cambian_costo": sum(1 for c in cambios if c["costo_nuevo"] is not None),
                "cambian_precios": sum(len(c["precios"]) for c in cambios),
            })
    elif accion == "aplicar":
        revision = request.session.get(SESION)
        if not revision or revision.get("token") != request.POST.get("token"):
            messages.error(request, "Esa revisión ya no está vigente: vuelve a subir el archivo.")
            return redirect("products:precios-masivos")
        actualizados = precios_masivos.aplicar(revision["cambios"], request.user)
        request.session.pop(SESION, None)
        messages.success(request, f"Se actualizaron los precios de {actualizados} producto{'s' if actualizados != 1 else ''}.")
        return redirect("products:precios-masivos")
    elif accion == "cancelar":
        request.session.pop(SESION, None)
        return redirect("products:precios-masivos")

    return render(request, "products/precios_masivos.html", contexto)
