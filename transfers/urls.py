# transfers/urls.py
from django.urls import path
from .views import (
    InitiateTransferView,
    ConfirmDebitView,
    CreditReceiverView,
    # launch_credit_from_webhook ,
)

urlpatterns = [
    path('initiate/', InitiateTransferView.as_view()),
    path('confirm/', ConfirmDebitView.as_view()),
    path('credit/', CreditReceiverView.as_view()),
    # path('webhook-paydunya/', paydunya_webhook, name='webhook'),
    # path('launch-credit/', launch_credit_from_webhook, name='launch-credit'),
    # path('update-status/', update_transfer_status, name='update-status'),


]









