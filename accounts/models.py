from django.contrib.auth.models import AbstractUser, UserManager as BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models


class UserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        PLATFORM_ADMIN = 'platform_admin', 'Platform Admin'
        TENANT_ADMIN = 'tenant_admin', 'Tenant Admin'
        TENANT_STAFF = 'tenant_staff', 'Tenant Staff'

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    groups = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='accounts_user_set',
        related_query_name='accounts_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='accounts_user_set',
        related_query_name='accounts_user',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ['email']

    def clean(self):
        super().clean()
        if self.role == self.Role.PLATFORM_ADMIN and self.tenant is not None:
            raise ValidationError('Platform admins cannot be assigned to a tenant.')
        if self.role in (self.Role.TENANT_ADMIN, self.Role.TENANT_STAFF) and self.tenant is None:
            raise ValidationError('Tenant admins and staff must be assigned to a tenant.')

    def save(self, *args, **kwargs):
        # is_staff is derived from role; only platform admins may access Django admin.
        self.is_staff = self.role == self.Role.PLATFORM_ADMIN
        super().save(*args, **kwargs)
