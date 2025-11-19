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





# 2. CONFIRMATION PAIEMENT (Wave, Orange, Moov)
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

        transfer.status = 'debited'
        transfer.paydunya_payment_ref = response.get('transaction_id', '')
        transfer.save()

        if transfer.from_wallet == 'wave-ci':
            wave_url = response.get('url')
            if wave_url:
                logger.info(f"WAVE REDIRECTION → {transfer.id}")
                return Response({
                    "message": "Redirigez vers Wave pour payer",
                    "redirect_url": wave_url,
                    "status": "debited",
                    "info": "Le crédit se lancera automatiquement après paiement Wave"
                })

        # Orange / Moov / MTN → crédit immédiat
        self._launch_credit(transfer)
        return Response({"message": "Paiement réussi ! Crédit en cours...", "status": "disbursing"})

    def _launch_credit(self, transfer):
        client = PayDunyaClient()
        try:
            disburse = client.disburse_create(
                phone=transfer.to_phone,
                amount=int(transfer.amount_sent),
                mode=transfer.to_wallet,
                callback_url=callback_url,  # ngrok ou prod
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
        except Exception as e:
            logger.error(f"ERREUR LANCEMENT CRÉDIT → {e}")


# 3. WEBHOOK UNIQUE → GÈRE WAVE + DÉBOURSEMENT (100% AUTOMATIQUE)
@csrf_exempt
def paydunya_webhook(request):
    logger.info("WEBHOOK PAYDUNYA REÇU")

    if request.method != 'POST':
        return JsonResponse({"status": "ok"}, status=200)

    try:
        data = json.loads(request.body)
        logger.info(f"WEBHOOK DATA → {data}")
    except:
        return JsonResponse({"status": "ok"}, status=200)

    # PAIEMENT WAVE CONFIRMÉ
    if data.get('event') == 'invoice_status' and data.get('status') == 'completed':
        token = data.get('invoice_token')
        if token:
            try:
                transfer = Transfer.objects.get(paydunya_invoice_token=token, status='debited')
                logger.info(f"WAVE PAIEMENT CONFIRMÉ → Lancement crédit pour transfert {transfer.id}")
                ConfirmDebitView()._launch_credit(transfer)  # Réutilise la fonction
            except Transfer.DoesNotExist:
                logger.warning("Transfert non trouvé ou déjà traité")
            except Exception as e:
                logger.error(f"ERREUR WEBHOOK WAVE → {e}")

    # STATUT DÉBOURSEMENT
    disburse_id = data.get('disburse_id')
    if disburse_id:
        try:
            transfer = Transfer.objects.get(disburse_id=disburse_id)
            client = PayDunyaClient()
            check = client.check_status(transfer.disburse_token)
            real_status = check.get('status') if check.get('response_code') == '00' else data.get('status')
            transfer.status = 'success' if real_status == 'success' else 'failed'
            transfer.save()
            logger.info(f"DÉBOURSEMENT FINAL → MB{transfer.id} = {transfer.status.upper()}")
        except Exception as e:
            logger.error(f"ERREUR WEBHOOK DÉBOURSEMENT → {e}")

    return JsonResponse({"status": "ok"}, status=200)

    
    
  
  
  
  
        
        
        
        
        
        
        
        
# transfers/views.py
class CreditReceiverView(APIView):
    def post(self, request):
        transfer_id = request.data.get('transfer_id')
        try:
            transfer = Transfer.objects.get(id=transfer_id, status='debited')
        except Transfer.DoesNotExist:
            return Response({"error": "Transfert non débité"}, status=404)

        client = PayDunyaClient()

        # URL webhook en prod (ngrok ou domaine)
        callback_url = "https://buudi.africa/api/v1/webhook-paydunya"

        disburse = client.disburse_create(
            phone=transfer.to_phone,
            amount=int(transfer.amount_sent),        # CORRIGÉ ICI
            mode=transfer.to_wallet,
            callback_url=callback_url,
            disburse_id=f"MB{transfer.id}"
        )

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
    
    



