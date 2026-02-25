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
    path('transfers/<int:transfer_id>/retry/', views.admin_transfer_retry, name='transfer_retry'),
    path('transfers/<int:transfer_id>/credit-retry/', views.admin_credit_retry, name='credit_retry'),
    path('recredits/', views.admin_recredits, name='recredits'),
    path('reconcile/', views.admin_reconcile, name='reconcile'),

    # === FRAIS DES OPÉRATEURS ===
    path('fees/', views.admin_operator_fees, name='fees'),
    path('fees/edit/<str:operator>/', views.admin_edit_operator_fee, name='edit_fee'),
    path('revenue-analytics/', views.admin_revenue_analytics, name='revenue_analytics'),


    # === PARAMÈTRES GÉNÉRAUX ===
    path('settings/', views.admin_settings, name='settings'),
    path('logout/', views.admin_logout, name='logout'),

    # === SUPPORT — API MOBILE (JSON) ===
    path('support/', views.api_support_list_create, name='api_support_list_create'),
    path('support/<int:ticket_id>/', views.api_support_detail, name='api_support_detail'),
    path('support/<int:ticket_id>/reply/', views.api_support_user_reply, name='api_support_user_reply'),

    # === SUPPORT — DASHBOARD HTML ===
    path('support-admin/', views.admin_support_list, name='support_list'),
    path('support-admin/<int:ticket_id>/', views.admin_support_detail, name='support_detail'),
    path('support-admin/<int:ticket_id>/reply/', views.admin_support_reply, name='support_reply'),
    path('support-admin/<int:ticket_id>/resolve/', views.admin_support_resolve, name='support_resolve'),

    # === DÉBOURSEMENT DIRECT (ADMIN) ===
    path('disburse/', views.admin_manual_disburse, name='manual_disburse'),
    path('disburse/<int:disburse_id>/check/', views.admin_check_disburse_status, name='disburse_check_status'),

    # === AUDIT & STATS LIVE ===
    path('audit-log/', views.admin_audit_log, name='audit_log'),
    path('dashboard-stats/', views.admin_dashboard_stats, name='dashboard_stats'),
]