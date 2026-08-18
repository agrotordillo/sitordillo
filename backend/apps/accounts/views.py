from django.views.generic import TemplateView


class LockoutView(TemplateView):
    template_name = 'accounts/lockout.html'
