from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from two_factor.admin import AdminSiteOTPRequiredMixin
from two_factor import urls as two_factor_urls
from unfold.sites import UnfoldAdminSite

from accounts.views import LoginView
from config.views import home


class OTPRequiredUnfoldAdminSite(AdminSiteOTPRequiredMixin, UnfoldAdminSite):
    """
    Combine django-two-factor-auth's OTP enforcement with Unfold's admin
    templates and extra URLs (e.g. global search).
    """
    pass


admin.site.__class__ = OTPRequiredUnfoldAdminSite

# Replace the default two-factor login view with our custom subclass.
two_factor_core_patterns, two_factor_app_name = two_factor_urls.urlpatterns
two_factor_urlpatterns = [
    path('account/login/', LoginView.as_view(), name='login'),
] + [
    p for p in two_factor_core_patterns
    if not (hasattr(p, 'pattern') and getattr(p.pattern, 'name', None) == 'login')
]

urlpatterns = [
    path('', home, name='home'),
    path('accounts/', include((two_factor_urlpatterns, two_factor_app_name))),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += [path('__reload__/', include('django_browser_reload.urls'))]
