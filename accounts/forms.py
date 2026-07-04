from django.contrib.auth.forms import UserChangeForm
from accounts.models import User


class UserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'tenant', 'is_active')
