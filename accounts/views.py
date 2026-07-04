from django.urls import resolve, Resolver404
from django.utils.http import url_has_allowed_host_and_scheme
from two_factor.views import LoginView as BaseLoginView


class LoginView(BaseLoginView):
    """
    Custom two-factor login view that redirects platform admins without a
    configured OTP device to the 2FA setup page when they were originally
    headed to the Django admin site.
    """

    def get_success_url(self):
        url = super().get_success_url()
        if self.requires_otp_setup(url):
            self.request.session['next'] = url
            return 'two_factor:setup'
        return url

    def requires_otp_setup(self, url):
        user = self.get_user()
        if not user or not user.is_authenticated:
            return False
        if not getattr(user, 'is_staff', False):
            return False
        if user_has_otp_device(user):
            return False
        return is_admin_path(url)


def user_has_otp_device(user):
    from django_otp import devices_for_user
    return any(devices_for_user(user))


def is_admin_path(url):
    if not url:
        return False
    try:
        match = resolve(url)
    except Resolver404:
        return False
    # Check whether the resolved URL is under the Django admin namespace.
    return match.namespaces and 'admin' in match.namespaces
