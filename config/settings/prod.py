from config.settings.base import *
from dj_database_url import parse as db_url

DEBUG = env.bool('DEBUG', default=False)
SECRET_KEY = env.str('SECRET_KEY')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')
INTERNAL_IPS = env.list('INTERNAL_IPS')

SSL_REDIRECT = env.bool('SSL_REDIRECT', default=True)
HSTS_INCLUDE_SUBDOMAINS = env.bool('HSTS_INCLUDE_SUBDOMAINS', default=True)
SSL_PROXY_HEADER = env.list('SSL_PROXY_HEADER', default=['HTTP_X_FORWARDED_PROTO', 'https'])
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)

DATABASES = {
    'default': db_url(env.str('DATABASE_URL'))
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env.str('EMAIL_HOST')
EMAIL_PORT = env.int('EMAIL_PORT')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS')
EMAIL_HOST_USER = env.str('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env.str('EMAIL_HOST_PASSWORD')

