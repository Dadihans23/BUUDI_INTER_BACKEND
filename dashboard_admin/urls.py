from django.urls import path
from . import views

app_name = 'custom_admin'

urlpatterns = [
    # === PAGE D'ACCUEIL & DASHBOARD ===
    path('', views.admin_login, name='login'),  # /admin/ → dashboard
    path('dashboard/', views.admin_dashboard, name='dashboard'),  # Redondant mais pratique

    # === UTILISATEURS ===
    path('users/', views.admin_users, name='users'),
    path('users/create/', views.admin_user_create, name='user_create'),
    path('users/<int:user_id>/', views.admin_user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views.admin_user_edit, name='user_edit'),
    # path('users/<int:user_id>/delete/', views.admin_user_delete, name='user_delete'),

    # === TRANSFERTS (la fonctionnalité principale) ===
    path('transfers/', views.admin_transfers, name='transfers'),
    path('transfers/<int:transfer_id>/', views.admin_transfer_detail, name='transfer_detail'),
    path('transfers/<int:transfer_id>/edit/', views.admin_transfer_edit, name='transfer_edit'),
    path('transfers/<int:transfer_id>/delete/', views.admin_transfer_delete, name='transfer_delete'),
    path('transfers/<int:transfer_id>/retry/', views.admin_transfer_retry, name='transfer_retry'),  # Si besoin de relancer

    # === FRAIS DES OPÉRATEURS ===
    path('fees/', views.admin_operator_fees, name='fees'),
    path('fees/edit/<str:operator>/', views.admin_edit_operator_fee, name='edit_fee'),
    path('revenue-analytics/', views.admin_revenue_analytics, name='revenue_analytics'),


    # === PARAMÈTRES GÉNÉRAUX ===
    path('settings/', views.admin_settings, name='settings'),
    path('logout/', views.admin_logout, name='logout'),


]