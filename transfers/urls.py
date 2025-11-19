# transfers/urls.py
from django.urls import path
from .views import (
    InitiateTransferView,
    ConfirmDebitView,
    CreditReceiverView,
    paydunya_webhook , 
)

urlpatterns = [
    path('initiate/', InitiateTransferView.as_view()),
    path('confirm/', ConfirmDebitView.as_view()),
    path('credit/', CreditReceiverView.as_view()),
    path('webhook-paydunya/', paydunya_webhook, name='webhook'),

]