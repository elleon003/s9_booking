from pathlib import Path
from environs import Env
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = Env()
env.read_env()


SECRET_KEY = env.str('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])
BASE_HOST = env.str('BASE_HOST', default='s9booking.local')


# Application definition

INSTALLED_APPS = [
    # Unfold 
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'unfold.contrib.inlines',

    # Default Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps (theme must come before two_factor so its templates override)
    'tailwind',
    'theme',

    # Two-factor authentication
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_email',
    'two_factor',
    'two_factor.plugins.email',

    # Local apps
    'accounts',
    'tenants',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'tenants.middleware.TenantMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'two_factor:login'
# Redirect to the 2FA profile page after login so platform admins without a
# configured device can set up 2FA before accessing /admin/.
LOGIN_REDIRECT_URL = 'two_factor:profile'

DEFAULT_FROM_EMAIL = env.str('DEFAULT_FROM_EMAIL', default='dev@s9booking.local')

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'

TAILWIND_APP_NAME = 'theme'


# Unfold admin configuration
# https://unfoldadmin.com/docs/configuration/settings/
UNFOLD = {
    'SITE_TITLE': _('S9 Booking'),
    'SITE_HEADER': _('S9 Booking'),
    'SITE_SUBHEADER': _('Administration'),
    'SITE_URL': '/',
    'COLORS': {
        'primary': {
            '50': '#F4F6F5',
            '100': '#E3E8E5',
            '200': '#C7D1CB',
            '300': '#A5B5AC',
            '400': '#82948B',
            '500': '#50665A',
            '600': '#45584E',
            '700': '#3A4A41',
            '800': '#2F3B35',
            '900': '#242D29',
        },
        'secondary': {
            '50': '#F8F8F0',
            '100': '#F2F2E8',
            '200': '#E8E8DA',
            '300': '#D9D9C7',
            '400': '#C4C4AE',
            '500': '#333333',
            '600': '#2E2E2E',
            '700': '#292929',
            '800': '#242424',
            '900': '#1F1F1F',
        },
        'terracotta': {
            '50': '#FDF4F0',
            '100': '#FAE6DE',
            '200': '#F5CCBC',
            '300': '#EBAA93',
            '400': '#D99077',
            '500': '#CC7755',
            '600': '#B56849',
            '700': '#9E5A3E',
            '800': '#874C34',
            '900': '#703E2B',
        },
    },
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': True,
        'navigation': [
            {
                'title': _('Management'),
                'separator': True,
                'items': [
                    {
                        'title': _('Dashboard'),
                        'icon': 'dashboard',
                        'link': reverse_lazy('admin:index'),
                    },
                    {
                        'title': _('Users'),
                        'icon': 'people',
                        'link': reverse_lazy('admin:accounts_user_changelist'),
                    },
                    {
                        'title': _('Tenants'),
                        'icon': 'domain',
                        'link': reverse_lazy('admin:tenants_tenant_changelist'),
                    },
                ],
            },
        ],
    },
    'STYLES': [
        lambda request: static('css/dist/styles.css'),
    ],
    'SCRIPTS': [
        lambda request: 'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Lora:wght@400;500;700&display=swap',
    ],
}