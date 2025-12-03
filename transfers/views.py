# transfers/views.py → VERSION FINALE 100% AUTOMATIQUE, NGROK/RENDER READY
from rest_framework.views import APIView
from rest_framework.response import Response
from users.models import UserProfile
from .models import Transfer, OperatorFees
from paydunya.client import PayDunyaClient
from decimal import Decimal
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from threading import Thread
import requests

logger = logging.getLogger('buudi')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s → %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

WALLET_MAP = {
    'orange': 'orange-money-ci',
    'wave': 'wave-ci',
    'mtn': 'mtn-ci',
    'moov': 'moov-ci',
}


class InitiateTransferView(APIView):
    def post(self, request):
        phone = request.headers.get('X-User-Phone')
        logger.info(f"INIT TRANSFERT → {phone}")

        try:
            user = UserProfile.objects.get(phone=phone)
        except UserProfile.DoesNotExist:
            return Response({"error": "Utilisateur inconnu"}, status=404)

        data = request.data
        amount = Decimal(data.get('amount', 0))
        from_key = data.get('from_wallet')
        to_key = data.get('to_wallet')

        if not all([amount > 0, from_key, to_key]):
            return Response({"error": "Données invalides"}, status=400)

        try:
            from_fee = OperatorFees.objects.get(operator=from_key)
            to_fee = OperatorFees.objects.get(operator=to_key)
        except OperatorFees.DoesNotExist:
            return Response({"error": "Frais non configurés"}, status=500)

        OUR_MARGIN = Decimal('1.5')
        payin = (amount * from_fee.payin_fee_percent / 100).quantize(Decimal('0.01'))
        payout = (amount * to_fee.payout_fee_percent / 100).quantize(Decimal('0.01'))
        our_fee = (amount * OUR_MARGIN / 100).quantize(Decimal('0.01'))
        total = (amount + payin + payout + our_fee).quantize(Decimal('0.01'))

        transfer = Transfer.objects.create(
            user=user,
            from_wallet=WALLET_MAP[from_key],
            to_wallet=WALLET_MAP[to_key],
            from_phone=data['from_phone'],
            to_phone=data['to_phone'],
            amount_requested=amount,
            amount_sent=amount,
            our_fee_percent=OUR_MARGIN,
            our_fee_amount=our_fee,
            payin_fee_amount=payin,
            payout_fee_amount=payout,
            total_debited=total,
            estimated_net_profit=our_fee,
            status='created'
        )

        client = PayDunyaClient()
        invoice = client.create_invoice(
            amount=int(total),
            description=f"Buudi Transfert #{transfer.id}"
        )

        if invoice.get('response_code') != '00':
            transfer.status = 'failed'
            transfer.save()
            return Response({"error": "Échec facture"}, status=500)

        transfer.paydunya_invoice_token = invoice['token']
        transfer.status = 'invoice_sent'
        transfer.save()

        return Response({
            "transfer_id": transfer.id,
            "amount_to_receive": float(amount),
            "total_to_pay": float(total),
            "our_commission": float(our_fee),
            "estimated_network_fees": float(payin + payout),
            "breakdown": {
                "Montant reçu": f"{amount} FCFA",
                "Frais réseau": f"~{payin + payout} FCFA",
                "Commission Buudi": f"{our_fee} FCFA",
                "Total débité": f"{total} FCFA"
            },
            "payment_token": invoice['token'],
            "message": "Paiement prêt – crédit automatique après validation"
        })


class ConfirmDebitView(APIView):
    def post(self, request):
        transfer_id = request.data.get('transfer_id')
        otp = request.data.get('otp', '')

        try:
            transfer = Transfer.objects.get(id=transfer_id, status='invoice_sent')
        except Transfer.DoesNotExist:
            return Response({"error": "Transfert invalide"}, status=404)

        client = PayDunyaClient()
        response = client.softpay(
            wallet=transfer.from_wallet,
            phone=transfer.from_phone,
            otp=otp,
            token=transfer.paydunya_invoice_token,
            fullname=transfer.user.name or "Client Buudi",
            email="contact@buudi.ci"
        )

        if not response.get('success'):
            return Response({"error": "Paiement échoué", "details": response}, status=400)

        # Wave → on attend le webhook
        if transfer.from_wallet == 'wave-ci':
            wave_url = response.get('url')
            if not wave_url:
                return Response({"error": "URL Wave manquante"}, status=500)
            transfer.status = 'pending_wave'
            transfer.save()
            
            # LANCE LE POLLING EN ARRIÈRE-PLAN
            Thread(target=_poll_wave_payment, args=(transfer,)).start()
    
            return Response({
                "message": "Redirigez vers Wave",
                "redirect_url": wave_url,
                "status": "pending_wave"
            })

        # Orange/Moov/MTN → débit immédiat → on lance le crédit tout de suite
        transfer.status = 'debited'
        transfer.paydunya_payment_ref = response.get('transaction_id', '')
        transfer.save()
        Thread(target=_launch_credit, args=(transfer,)).start()

        return Response({
            "message": "Paiement réussi ! Crédit en cours...",
            "status": "debited"
        })




@csrf_exempt
def _launch_credit(transfer):
    if transfer.status not in ['debited', 'pending_wave']:
        return

    client = PayDunyaClient()
    try:
        disburse = client.disburse_create(
            phone=transfer.to_phone,
            amount=int(transfer.amount_sent),
            mode=transfer.to_wallet,
            callback_url="https://buudi.africa/api/v1/webhook-paydunya",  # DYNAMIQUE
            disburse_id=f"MB{transfer.id}"
        )

        if disburse.get('response_code') == '00':
            submit = client.disburse_submit(disburse['disburse_token'], f"MB{transfer.id}")
            if submit.get('response_code') == '00':
                transfer.disburse_token = disburse['disburse_token']
                transfer.disburse_id = f"MB{transfer.id}"
                transfer.status = 'disbursing'
                transfer.save()
                logger.info(f"CRÉDIT AUTOMATIQUE LANCÉ → MB{transfer.id}")
                return

        transfer.status = 'failed'
        transfer.save()
        logger.error(f"ÉCHEC CRÉDIT → {disburse} | {submit}")
    except Exception as e:
        transfer.status = 'failed'
        transfer.save()
        logger.error(f"ERREUR FATALE CRÉDIT → {e}", exc_info=True)


  
import time

def _launch_credit(transfer):
    if transfer.status not in ['debited', 'pending_wave']:
        logger.info(f"Crédit ignoré – mauvais statut : {transfer.status}")
        return

    client = PayDunyaClient()

    try:
        # 1. Création du déboursement
        disburse = client.disburse_create(
            phone=transfer.to_phone,
            amount=int(transfer.amount_sent),
            mode=transfer.to_wallet,
            callback_url="https://buudi.africa/api/v1/webhook-paydunya",  # DYNAMIQUE
            disburse_id=f"MB{transfer.id}"
        )

        if disburse.get('response_code') != '00':
            transfer.status = 'failed'
            transfer.save()
            logger.error(f"ÉCHEC disburse_create → {disburse}")
            return

        # 2. Soumission
        submit = client.disburse_submit(disburse['disburse_token'], f"MB{transfer.id}")
        if submit.get('response_code') != '00':
            transfer.status = 'failed'
            transfer.save()
            logger.error(f"ÉCHEC disburse_submit → {submit}")
            return

        # 3. On sauvegarde le token et on passe en disbursing
        transfer.disburse_token = disburse['disburse_token']
        transfer.disburse_id = f"MB{transfer.id}"
        transfer.status = 'disbursing'
        transfer.save()

        logger.info(f"CRÉDIT LANCÉ → MB{transfer.id} | Token: {disburse['disburse_token'][-10:]}... | Polling en cours...")

        # 4. POLLING ACTIF → on vérifie toutes les 3 sec pendant max 60 sec
        max_attempts = 20  # 20 × 3 sec = 60 sec
        for attempt in range(max_attempts):
            time.sleep(3)
            
            check = client.check_status(disburse['disburse_token'])
            logger.info(f"Check status tentative {attempt + 1}/20 → {check}")

            if check.get('response_code') == '00':
                real_status = check.get('status')
                if real_status == 'success':
                    transfer.status = 'success'
                    transfer.save()
                    logger.info(f"SUCCÈS CONFIRMÉ PAR POLLING → MB{transfer.id}")
                    return
                elif real_status == 'failed':
                    transfer.status = 'failed'
                    transfer.save()
                    logger.error(f"ÉCHEC CONFIRMÉ PAR POLLING → MB{transfer.id}")
                    return

        # Si après 60 sec toujours rien → on marque en attente mais on ne bloque pas
        logger.warning(f"Timeout polling – statut reste 'disbursing' pour MB{transfer.id} (le webhook finira le job si il arrive)")

    except Exception as e:
        transfer.status = 'failed'
        transfer.save()
        logger.error(f"ERREUR FATALE CRÉDIT → {e}", exc_info=True)        
        
        
        
def _poll_wave_payment(transfer):
    client = PayDunyaClient()
    token = transfer.paydunya_invoice_token
    max_attempts = 40  # 40 × 3 sec = 2 minutes max

    for attempt in range(max_attempts):
        time.sleep(4)
        
        status_check = client.check_invoice_status(token)
        logger.info(f"Polling Wave paiement tentative {attempt + 1} → {status_check.get('status')}")

        if status_check.get('status') == 'completed':
            logger.info(f"WAVE PAIEMENT CONFIRMÉ PAR POLLING → Lancement crédit pour MB{transfer.id}")
            _launch_credit(transfer)  # On réutilise ta fonction existante
            return
        elif status_check.get('status') in ['cancelled', 'failed']:
            transfer.status = 'failed'
            transfer.save()
            logger.warning(f"WAVE PAIEMENT ANNULÉ/ÉCHEC → MB{transfer.id}")
            return

    # Si après 2 min toujours rien → on abandonne (l'utilisateur a fermé l'app)
    transfer.status = 'failed'
    transfer.save()
    logger.warning(f"Timeout polling Wave – paiement non confirmé pour MB{transfer.id}")        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
class CreditReceiverView(APIView):
    def post(self, request):
        transfer_id = request.data.get('transfer_id')
        try:
            transfer = Transfer.objects.get(id=transfer_id)
        except Transfer.DoesNotExist:
            return Response({"error": "Transfert non débité"}, status=404)

        client = PayDunyaClient()

        # URL webhook en prod (ngrok ou domaine)
        callback_url = "https://buudi.africa/api/v1/webhook-paydunya"
        try:
            disburse = client.disburse_create(
                        phone=transfer.to_phone,
                        amount=int(transfer.amount_sent),        # CORRIGÉ ICI
                        mode=transfer.to_wallet,
                        callback_url=callback_url,
                        disburse_id=f"MB{transfer.id}"
                    )            
        except requests.exceptions.Timeout:
            return Response({"error": "PayDunya ne répond pas (timeout)"}, status=504)
        except Exception as e:
            return Response({"error": "Erreur PayDunya", "details": str(e)}, status=500)

        if disburse.get('response_code') != '00':
            return Response({
                "error": "Échec création déboursement",
                "details": disburse
            }, status=500)

        submit = client.disburse_submit(disburse['disburse_token'], f"MB{transfer.id}")

        if submit.get('response_code') == '00':
            status = submit.get('status', 'pending')
            transfer.disburse_token = disburse['disburse_token']
            transfer.disburse_id = f"MB{transfer.id}"
            transfer.status = 'disbursing' if status == 'pending' else 'success'
            transfer.save()
            return Response({
                "message": "Crédit lancé",
                "status": transfer.status,
                "disburse_id": f"MB{transfer.id}"
            })

        transfer.status = 'failed'
        transfer.save()
        return Response({"error": "Échec soumission", "details": submit}, status=500)
    
    



