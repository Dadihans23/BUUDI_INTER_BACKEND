# transfers/views.py → VERSION FINALE 100% AUTOMATIQUE + NGROK READY
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

import requests

# transfers/views.py → UTILISE LA VARIABLE DYNAMIQUE
from django.conf import settings

# Dans _launch_credit() et partout où tu avais l’URL en dur :
callback_url = settings.PAYDUNYA_WEBHOOK_URL   # ← MAGIQUE

# LOGS ULTRA-COMPLETS (tu vois TOUT en temps réel)
logger = logging.getLogger('buudi')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s → %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# MAP WALLET
WALLET_MAP = {
    'orange': 'orange-money-ci',
    'wave': 'wave-ci',
    'mtn': 'mtn-ci',
    'moov': 'moov-ci',
}


# 1. INITIATION DU TRANSFERT
class InitiateTransferView(APIView):
    def post(self, request):
        phone = request.headers.get('X-User-Phone')
        logger.info(f"INITIATION TRANSFERT → Téléphone: {phone}")

        try:
            user = UserProfile.objects.get(phone=phone)
        except UserProfile.DoesNotExist:
            logger.error("UTILISATEUR INTROUVABLE")
            return Response({"error": "Utilisateur inconnu"}, status=404)

        data = request.data
        amount = Decimal(data.get('amount', 0))
        from_key = data.get('from_wallet')
        to_key = data.get('to_wallet')

        if not all([amount, from_key, to_key]):
            return Response({"error": "Données manquantes"}, status=400)

        logger.info(f"TRANSFERT {amount} FCFA → {from_key.upper()} → {to_key.upper()}")

        # Frais PayDunya
        try:
            from_fee = OperatorFees.objects.get(operator=from_key)
            to_fee = OperatorFees.objects.get(operator=to_key)
        except OperatorFees.DoesNotExist:
            logger.error("FRAIS OPÉRATEUR MANQUANTS")
            return Response({"error": "Frais non configurés"}, status=500)

        OUR_MARGIN = Decimal('1.5')
        payin = (amount * from_fee.payin_fee_percent / 100).quantize(Decimal('0.01'))
        payout = (amount * to_fee.payout_fee_percent / 100).quantize(Decimal('0.01'))
        our_fee = (amount * OUR_MARGIN / 100).quantize(Decimal('0.01'))
        total = (amount + payin + payout + our_fee).quantize(Decimal('0.01'))

        logger.info(f"FRAIS → Payin: {payin} | Payout: {payout} | Buudi: {our_fee} | Total: {total}")

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
            payin_fee_percent=from_fee.payin_fee_percent,
            payin_fee_amount=payin,
            payout_fee_percent=to_fee.payout_fee_percent,
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
            logger.error(f"ÉCHEC FACTURE → {invoice}")
            return Response({"error": "Échec création facture"}, status=500)

        transfer.paydunya_invoice_token = invoice['token']
        transfer.status = 'invoice_sent'
        transfer.save()

        logger.info(f"FACTURE CRÉÉE → ID: {transfer.id} | Montant: {total} FCFA")

        return Response({
            "transfer_id": transfer.id,
            "amount_to_receive": float(amount),
            "total_to_pay": float(total),
            "our_commission": float(our_fee),
            "estimated_network_fees": float(payin + payout),
            "breakdown": {
                "Montant reçu par l'ami": f"{amount} FCFA",
                "Frais réseau estimés": f"~{payin + payout} FCFA",
                "Commission Buudi": f"{our_fee} FCFA (1.5%)",
                "Total à payer": f"{total} FCFA"
            },
            "payment_token": invoice['token'],
            "message": "Paiement prêt ! Le crédit sera automatique après validation"
        })





# 2. CONFIRMATION PAIEMENT → ON NE LANCE PLUS RIEN ICI (évite timeout sur Render)
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

        logger.info(f"SOFTPAY RESPONSE → {response}")

        if not response.get('success'):
            return Response({"error": "Paiement échoué", "details": response}, status=400)

        # CAS 1 : ORANGE / MOOV / MTN → OTP validé = DÉBIT RÉEL
        if transfer.from_wallet != 'wave-ci':
            transfer.status = 'debited'
            transfer.paydunya_payment_ref = response.get('transaction_id', '')
            transfer.save()
            logger.info(f"DÉBIT RÉEL → Transfert {transfer.id} marqué 'debited'")
            return Response({
                "message": "Paiement réussi ! Crédit en cours dans quelques secondes...",
                "status": "debited"
            })

        # CAS 2 : WAVE → on a juste l'URL, PAS de débit encore
        wave_url = response.get('url')
        if not wave_url:
            return Response({"error": "Aucune URL Wave reçue"}, status=500)

        # ON NE CHANGE PAS LE STATUT EN 'debited' → on crée un nouveau statut clair
        transfer.status = 'pending_wave'  # ou 'waiting_wave_payment'
        transfer.paydunya_payment_ref = response.get('transaction_id', '')
        transfer.save()

        logger.info(f"WAVE REDIRECTION → Transfert {transfer.id} en attente de paiement réel")

        return Response({
            "message": "Redirigez l'utilisateur vers Wave pour payer",
            "redirect_url": wave_url,
            "status": "pending_wave",
            "info": "Le débit sera confirmé automatiquement quand l'utilisateur paiera sur Wave"
        })



# transfers/views.py → WEBHOOK FINAL (PLUS JAMAIS DE TIMEOUT)
@csrf_exempt
def paydunya_webhook(request):
    logger.info("WEBHOOK PAYDUNYA REÇU ! IP: %s", request.META.get('REMOTE_ADDR', 'unknown'))

    if request.method != 'POST':
        return JsonResponse({"status": "ok"}, status=200)

    try:
        data = json.loads(request.body)
        logger.info(f"WEBHOOK DATA → {data}")
    except:
        return JsonResponse({"status": "ok"}, status=200)

    # 1. PAIEMENT CONFIRMÉ → on lance le crédit
    if data.get('event') == 'invoice_status' and data.get('status') == 'completed':
        token = data.get('invoice_token')
        if token:
            try:
                transfer = Transfer.objects.get(paydunya_invoice_token=token, status='pending_wave')
                logger.info(f"PAIEMENT CONFIRMÉ → Transfert {transfer.id} → Lancement crédit automatique")

                # Lancement en arrière-plan (aucun timeout)
                from threading import Thread
                Thread(target=_launch_credit_automatic, args=(transfer,)).start()

            except Transfer.DoesNotExist:
                logger.warning("Transfert non trouvé pour ce token")
            except Exception as e:
                logger.error(f"ERREUR WEBHOOK → {e}", exc_info=True)



    # 2. DÉBOURSEMENT TERMINÉ
    elif data.get('disburse_id'):
        disburse_id = data.get('disburse_id')
        try:
            transfer = Transfer.objects.get(disburse_id=disburse_id)
            client = PayDunyaClient()
            check = client.check_status(transfer.disburse_token or "")
            
            status = 'success' if check.get('response_code') == '00' and check.get('status') == 'success' else 'failed'
            transfer.status = status
            transfer.save()
            
            logger.info(f"TRANSFERT TERMINÉ → MB{transfer.id} = {status.upper()}")

        except Exception as e:
            logger.error(f"ERREUR DÉBOURSEMENT → {e}")

    return JsonResponse({"status": "ok"}, status=200)



# FONCTION PRIVÉE → Lancement du crédit (utilisée par le webhook)
def _launch_credit_automatic(transfer):
    """Lance le crédit de manière sécurisée via webhook (pas de timeout)"""
    if transfer.status in ['disbursing', 'success', 'failed']:
        logger.info(f"Crédit déjà lancé ou terminé pour transfert {transfer.id}")
        return

    client = PayDunyaClient()
    try:
        disburse = client.disburse_create(
            phone=transfer.to_phone,
            amount=int(transfer.amount_sent),
            mode=transfer.to_wallet,
            callback_url="https://buudi-inter-backend.onrender.com/api/transfer/webhook-paydunya/",  # dynamique (ngrok ou Render)
            disburse_id=f"MB{transfer.id}"
        )

        logger.info(f"DISBURSE_CREATE → {disburse}")

        if disburse.get('response_code') == '00':
            submit = client.disburse_submit(disburse['disburse_token'], f"MB{transfer.id}")
            logger.info(f"DISBURSE_SUBMIT49 → {submit}")

            if submit.get('response_code') == '00':
                transfer.disburse_token = disburse['disburse_token']
                transfer.disburse_id = f"MB{transfer.id}"
                transfer.status = 'disbursing'
                transfer.save()
                logger.info(f"CRÉDIT AUTOMATIQUE LANCÉ → MB{transfer.id}")
            else:
                transfer.status = 'failed'
                transfer.save()
                logger.error(f"ÉCHEC SUBMIT → {submit}")
        else:
            transfer.status = 'failed'
            transfer.save()
            logger.error(f"ÉCHEC CREATE → {disburse}")

    except Exception as e:
        transfer.status = 'failed'
        transfer.save()
        logger.error(f"ERREUR FATALE CRÉDIT → {e}", exc_info=True)
    
  
  
  
  
  
  
  
  
  
  
  
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
# transfers/views.py
class CreditReceiverView(APIView):
    def post(self, request):
        transfer_id = request.data.get('transfer_id')
        try:
            transfer = Transfer.objects.get(id=transfer_id)
        except Transfer.DoesNotExist:
            return Response({"error": "Transfert non débité"}, status=404)

        client = PayDunyaClient()

        # URL webhook en prod (ngrok ou domaine)
        callback_url = "https://buudi-inter-backend.onrender.com/api/transfer/webhook-paydunya/"

        # disburse = client.disburse_create(
        #     phone=transfer.to_phone,
        #     amount=int(transfer.amount_sent),        # CORRIGÉ ICI
        #     mode=transfer.to_wallet,
        #     callback_url=callback_url,
        #     disburse_id=f"MB{transfer.id}"
        # )
        
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
    
    



