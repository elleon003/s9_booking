from config.settings.base import *

DEBUG = env.bool('DEBUG', default=True)
SECRET_KEY = env.str('SECRET_KEY', default='django-insecure-b12bq^0dr1$@iv!gr8&2@uq17xld0rg5j$$f$t3jvwzo0t=th!')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '::1'])
INTERNAL_IPS = env.list('INTERNAL_IPS', default=['127.0.0.1', 'localhost'])


INSTALLED_APPS += [
    'django_browser_reload',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'