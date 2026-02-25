"""money_transfer URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from dashboard_admin.views import landing_page
from transfers.views import paydunya_webhook

urlpatterns = [
    path('', landing_page, name='landing'),
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/transfer/', include('transfers.urls')),
    path('api/dashboard/', include('dashboard_admin.urls')),

    # Alias legacy : certains endroits hardcodent /api/v1/webhook-paydunya
    path('api/v1/webhook-paydunya', paydunya_webhook, name='webhook-paydunya-v1'),
]


