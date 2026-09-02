from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView, View

from apps.core.permissions import SuperuserRequiredMixin
from .forms import AsignacionSucursalForm, AsignacionSucursalInlineFormSet, UsuarioCreateForm
from .models import AsignacionSucursal

User = get_user_model()


class LockoutView(TemplateView):
    template_name = 'accounts/lockout.html'


# Alta de usuarios: mismo invariante que AsignacionSucursal, exclusivo del
# Administrador (ver nota abajo).
class UsuarioListView(SuperuserRequiredMixin, ListView):
    model = User
    template_name = "accounts/usuario_list.html"
    context_object_name = "usuarios"
    extra_context = {"active_module": "system"}

    def get_queryset(self):
        return super().get_queryset().prefetch_related("groups").order_by("username")


class UsuarioCreateView(SuperuserRequiredMixin, CreateView):
    model = User
    form_class = UsuarioCreateForm
    template_name = "accounts/usuario_form.html"
    success_url = reverse_lazy("accounts:usuario-list")
    success_message = "Usuario creado correctamente."
    extra_context = {"active_module": "system"}

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = AsignacionSucursalInlineFormSet(self.request.POST, instance=self.object, prefix="asignaciones")
            else:
                data["formset"] = AsignacionSucursalInlineFormSet(instance=self.object, prefix="asignaciones")
        return data

    def form_valid(self, form):
        formset = AsignacionSucursalInlineFormSet(self.request.POST, instance=User(), prefix="asignaciones")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible crear el usuario. Revisa los campos.")
        return super().form_invalid(form)


class UsuarioToggleActivoView(SuperuserRequiredMixin, View):
    """Borrado lógico: un usuario nunca se elimina, solo se desactiva
    (is_active=False). Django ya bloquea el login de un usuario inactivo
    por su cuenta, y sus asignaciones de sucursal se conservan por si se
    reactiva después."""

    def post(self, request, pk):
        usuario = get_object_or_404(User, pk=pk)
        if usuario.pk == request.user.pk:
            messages.error(request, "No puedes desactivar tu propia cuenta.")
            return redirect("accounts:usuario-list")

        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active"])
        if usuario.is_active:
            messages.success(request, f"Usuario {usuario.username} reactivado.")
        else:
            messages.success(request, f"Usuario {usuario.username} desactivado.")
        return redirect("accounts:usuario-list")


# Gestión de usuarios/permisos: capacidad exclusiva del Administrador (ver
# regla de negocio confirmada: nadie más puede dar de alta accesos). Se usa
# SuperuserRequiredMixin (is_superuser) en vez de un permiso de Django
# reasignable, porque esto es un invariante de negocio, no una capacidad
# que en algún momento tenga sentido delegar a un grupo.
class AsignacionSucursalListView(SuperuserRequiredMixin, ListView):
    model = AsignacionSucursal
    template_name = "accounts/asignacion_sucursal_list.html"
    context_object_name = "asignaciones"
    extra_context = {"active_module": "system"}

    def get_queryset(self):
        return super().get_queryset().select_related("usuario", "almacen")


class AsignacionSucursalCreateView(SuperuserRequiredMixin, SuccessMessageMixin, CreateView):
    model = AsignacionSucursal
    form_class = AsignacionSucursalForm
    template_name = "accounts/asignacion_sucursal_form.html"
    success_url = reverse_lazy("accounts:asignacion-sucursal-list")
    success_message = "Asignación creada correctamente."
    extra_context = {"active_module": "system"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la asignación. Revisa los campos.")
        return super().form_invalid(form)


class AsignacionSucursalUpdateView(SuperuserRequiredMixin, SuccessMessageMixin, UpdateView):
    model = AsignacionSucursal
    form_class = AsignacionSucursalForm
    template_name = "accounts/asignacion_sucursal_form.html"
    success_url = reverse_lazy("accounts:asignacion-sucursal-list")
    success_message = "Asignación actualizada correctamente."
    extra_context = {"active_module": "system"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la asignación. Revisa los campos.")
        return super().form_invalid(form)
