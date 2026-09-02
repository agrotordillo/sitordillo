from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import LoginForm
from .views import (
    AsignacionSucursalCreateView,
    AsignacionSucursalListView,
    AsignacionSucursalUpdateView,
    LockoutView,
    UsuarioCreateView,
    UsuarioListView,
    UsuarioToggleActivoView,
)

app_name = 'accounts'

urlpatterns = [
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='accounts/login.html',
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('lockout/', LockoutView.as_view(), name='lockout'),
    path('usuarios/', UsuarioListView.as_view(), name='usuario-list'),
    path('usuarios/crear/', UsuarioCreateView.as_view(), name='usuario-create'),
    path('usuarios/<int:pk>/toggle-activo/', UsuarioToggleActivoView.as_view(), name='usuario-toggle-activo'),
    path('usuarios/sucursales/', AsignacionSucursalListView.as_view(), name='asignacion-sucursal-list'),
    path('usuarios/sucursales/crear/', AsignacionSucursalCreateView.as_view(), name='asignacion-sucursal-create'),
    path(
        'usuarios/sucursales/<int:pk>/editar/',
        AsignacionSucursalUpdateView.as_view(),
        name='asignacion-sucursal-update',
    ),
]
