# payments/paydunya.py
import requests
from django.conf import settings

class PayDunyaAPI:
    BASE_URL = "https://app.paydunya.com"
    HEADERS = {
        "PAYDUNYA-MASTER-KEY": settings.PAYDUNYA_MASTER_KEY,
        "PAYDUNYA-PRIVATE-KEY": settings.PAYDUNYA_PRIVATE_KEY,
        "PAYDUNYA-TOKEN": settings.PAYDUNYA_TOKEN,
        "Content-Type": "application/json"
    }

    # === 1. CRÉER INVOICE (commun à tous) ===
    @staticmethod
    def create_invoice(amount, description="Transfert inter-réseau"):
        url = f"{PayDunyaAPI.BASE_URL}/api/v1/checkout-invoice/create"
        data = {
            "invoice": {"total_amount": amount, "description": description},
            "store": {"name": "MonApp Transfert"}
        }
        r = requests.post(url, json=data, headers=PayDunyaAPI.HEADERS)
        return r.json()

    # === 2. PAYIN PAR OPÉRATEUR ===
    @staticmethod
    def confirm_payin(operator, **kwargs):
        endpoints = {
            "orange": "/api/v1/softpay/orange-money-ci",
            "mtn": "/api/v1/softpay/mtn-ci",
            "moov": "/api/v1/softpay/moov-ci",
            "wave": "/api/v1/softpay/wave-ci"
        }
        url = f"{PayDunyaAPI.BASE_URL}{endpoints[operator]}"
        r = requests.post(url, json=kwargs, headers=PayDunyaAPI.HEADERS)
        return r.json()

    # === 3. PAYOUT (déboursement) ===
    @staticmethod
    def initiate_disburse(phone, amount, mode, callback_url, disburse_id=None):
        url = f"{PayDunyaAPI.BASE_URL}/api/v2/disburse/get-invoice"
        data = {
            "account_alias": phone,
            "amount": amount,
            "withdraw_mode": f"{mode}-ci",
            "callback_url": callback_url
        }
        if disburse_id:
            data["disburse_id"] = disburse_id
        r = requests.post(url, json=data, headers=PayDunyaAPI.HEADERS)
        return r.json()

    @staticmethod
    def submit_disburse(token, disburse_id=None):
        url = f"{PayDunyaAPI.BASE_URL}/api/v2/disburse/submit-invoice"
        data = {"disburse_invoice": token}
        if disburse_id:
            data["disburse_id"] = disburse_id
        r = requests.post(url, json=data, headers=PayDunyaAPI.HEADERS)
        return r.json()

    @staticmethod
    def check_disburse_status(token):
        url = f"{PayDunyaAPI.BASE_URL}/api/v2/disburse/check-status"
        r = requests.post(url, json={"disburse_invoice": token}, headers=PayDunyaAPI.HEADERS)
        return r.json()