from django.shortcuts import render


def home(request):
    return render(request, 'home.html', {'tenant': getattr(request, 'tenant', None)})
