# paydunya/client.py
import requests
from django.conf import settings

callback_url = settings.PAYDUNYA_WEBHOOK_URL   # ← MAGIQUE


class PayDunyaClient:
    def __init__(self):
        self.base_url = settings.PAYDUNYA['BASE_URL']
        self.headers = {
            "Content-Type": "application/json",
            "PAYDUNYA-MASTER-KEY": settings.PAYDUNYA['MASTER_KEY'],
            "PAYDUNYA-PRIVATE-KEY": settings.PAYDUNYA['PRIVATE_KEY'],
            "PAYDUNYA-TOKEN": settings.PAYDUNYA['TOKEN'],
        }

    
    
    def create_invoice(self, amount, description):
        url = f"{self.base_url}/api/v1/checkout-invoice/create"
        data = {
            "invoice": {
                "total_amount": amount,
                "description": description,
                "callback_url": callback_url # DOIT ÊTRE ICI !
            },
            "store": {
                "name": "Buudi Transfert",
                "website_url": "https://buudi.africa"
            }
        }
        return requests.post(url, json=data, headers=self.headers).json()
    
    
    
    

    # paydunya/client.py
    def softpay(self, wallet, phone, otp, token, fullname, email):
        wallet_key = wallet.replace('-', '_')  # ex: wave_ci
        wallet_endpoint = wallet  # ex: wave-ci

        url = f"{self.base_url}/api/v1/softpay/{wallet_endpoint}"

        # === DONNÉES DE BASE ===
        data = {
            f"{wallet_key}_email": email,
        }

        # === SPÉCIFIQUE PAR WALLET ===
        if 'wave' in wallet:
            # WAVE : fullName (camelCase) + phone + payment_token
            data[f"{wallet_key}_fullName"] = fullname
            data[f"{wallet_key}_phone"] = phone
            data[f"{wallet_key}_payment_token"] = token
        else:
            # ORANGE/MOOV/MTN : customer_fullname + phone_number + otp
            data[f"{wallet_key}_customer_fullname"] = fullname
            data[f"{wallet_key}_phone_number"] = phone
            data[f"{wallet_key}_otp"] = otp or ""
            data["payment_token"] = token

        # === DEBUG ===
        print("DEBUG SOFTPAY DATA:", data)

        response = requests.post(url, json=data, headers=self.headers)

        print("\n=== PAYDUNYA SOFTPAY DEBUG ===")
        print(f"URL: {url}")
        print(f"Data: {data}")
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text[:500]}")
        print("===============================\n")

        # === GESTION ERREURS ===
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}",
                "raw": response.text
            }

        if not response.text.strip():
            return {
                "success": False,
                "error": "Réponse vide de PayDunya",
                "raw": ""
            }

        try:
            return response.json()
        except:
            return {
                "success": False,
                "error": "JSON invalide",
                "raw": response.text
            }


    def disburse_create(self, phone, amount, mode, callback_url, disburse_id=None):
        url = f"{self.base_url}/api/v2/disburse/get-invoice"
        data = {
            "account_alias": phone,
            "amount": int(amount),
            "withdraw_mode": mode,
            "callback_url": callback_url
        }
        if disburse_id:
            data["disburse_id"] = disburse_id
        return requests.post(url, json=data, headers=self.headers).json()

    def disburse_submit(self, token, disburse_id=None):
        url = f"{self.base_url}/api/v2/disburse/submit-invoice"
        data = {"disburse_invoice": token}
        if disburse_id:
            data["disburse_id"] = disburse_id
        return requests.post(url, json=data, headers=self.headers).json()

    def check_status(self, token):
        url = f"{self.base_url}/api/v2/disburse/check-status"
        return requests.post(url, json={"disburse_invoice": token}, headers=self.headers).json()
    
    
    
    
    
    