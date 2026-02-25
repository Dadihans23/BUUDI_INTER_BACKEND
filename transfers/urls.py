# transfers/urls.py
from django.urls import path
from .views import (
    InitiateTransferView,
    ConfirmDebitView,
    CreditReceiverView,
    FeesConfigView,
    TransferStatusView,
    UserTransactionsView,
    paydunya_webhook,
)

urlpatterns = [
    path('initiate/', InitiateTransferView.as_view()),
    path('confirm/', ConfirmDebitView.as_view()),
    path('credit/', CreditReceiverView.as_view()),
    path('fees-config/', FeesConfigView.as_view()),
    path('<int:transfer_id>/status/', TransferStatusView.as_view(), name='transfer-status'),
    path('my-transactions/', UserTransactionsView.as_view(), name='user-transactions'),

    # Webhook Paydunya : callback automatique après déboursement
    path('webhook-paydunya/', paydunya_webhook, name='webhook-paydunya'),
]








