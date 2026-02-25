# transfers/views.py → VERSION FINALE 100% AUTOMATIQUE, NGROK/RENDER READY
from rest_framework.views import APIView
from rest_framework.response import Response
from users.models import UserProfile
from .models import Transfer, OperatorFees
from .serializers import TransferSerializer
from paydunya.client import PayDunyaClient
from decimal import Decimal
import logging
import time
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
    
    # 🇸🇳 Sénégal
    'orange-sénégal': 'orange-money-senegal',
    'wave-sénégal': 'wave-senegal',
    'free-money-sénégal': 'free-money-senegal',
    'emoney-sénégal': 'expresso-senegal',

    # 🇧🇯 Bénin
    'mtn-bénin': 'mtn-benin',
    'moov-bénin': 'moov-benin',

    # 🇹🇬 Togo
    'tmoney-togo': 't-money-togo',
    'moov-togo': 'moov-togo',

    # 🇧🇫 Burkina Faso
    'orange-faso': 'orange-money-burkina',
    'moov-faso': 'moov-burkina-faso',

    # 🇲🇱 Mali
    'orange-mali': 'orange-money-mali'
}


from transfers.throttles import InitiateThrottle, ConfirmThrottle, CreditThrottle


class InitiateTransferView(APIView):
    throttle_classes = [InitiateThrottle]

    def post(self, request):
    
        phone = request.headers.get('X-User-Phone')
        name = request.headers.get('X-User-Name', None)

        logger.info(f"INIT TRANSFERT → {phone} | Nom reçu : {name}")

        if not phone:
            return Response({"error": "Numéro manquant"}, status=400)

        # Création automatique si nécessaire
        user, created = UserProfile.objects.get_or_create(
            phone=phone,
            defaults={"name": name or f"User_{phone}"}
        )

        if created:
            logger.info(f"Nouvel utilisateur créé : {user.phone} ({user.name})")
        else:
            logger.info(f"Utilisateur existant : {user.phone} ({user.name})")

        data = request.data
        amount = Decimal(data.get('amount', 0))
        from_key = data.get('from_wallet')
        to_key = data.get('to_wallet')  # ex: "MTN MoMo BJ"
        

        try:
            from_fee = OperatorFees.objects.get(operator=from_key)
        except OperatorFees.DoesNotExist:
            return Response({"error": f"Opérateur '{from_key}' non configuré. Contactez le support."}, status=500)

        try:
            to_fee = OperatorFees.objects.get(operator=to_key)
        except OperatorFees.DoesNotExist:
            return Response({"error": f"Opérateur destinataire '{to_key}' non configuré. Contactez le support."}, status=500)

        OUR_MARGIN = Decimal('1.5')
        our_fee_percent = from_fee.our_fee_percent
        payin = (amount * from_fee.payin_fee_percent / 100).quantize(Decimal('0.01'))
        payout = (amount * to_fee.payout_fee_percent / 100).quantize(Decimal('0.01'))
        our_fee = (amount * our_fee_percent / 100).quantize(Decimal('0.01'))
        total = (amount + payin + payout + our_fee).quantize(Decimal('0.01'))

        transfer = Transfer.objects.create(
            user=user,
            from_wallet=WALLET_MAP[from_key],
            to_wallet=WALLET_MAP[to_key],
            from_phone=data['from_phone'],
            to_phone=data['to_phone'],
            amount_requested=amount,
            amount_sent=amount,
            our_fee_percent=our_fee_percent,
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
            return Response({"error": "Impossible de préparer le paiement. Réessayez dans quelques instants."}, status=500)

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
    throttle_classes = [ConfirmThrottle]

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
            logger.error(f"PAIEMENT ÉCHOUÉ → MB{transfer.id} → {response}")
            transfer.status = 'failed'
            transfer.save()
            paydunya_msg = response.get('message', '')
            user_msg = paydunya_msg if paydunya_msg else "Paiement refusé par l'opérateur. Vérifiez votre solde ou réessayez."
            return Response({"error": user_msg}, status=400)

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

        # 2. ORANGE / MOOV : débit immédiat après OTP/PIN (popup ou OTP saisi)
        elif transfer.from_wallet in ['orange-money-ci', 'moov-ci']:
            transfer.status = 'debited'
            transfer.paydunya_payment_ref = response.get('transaction_id', '')
            transfer.save()
            Thread(target=_launch_credit, args=(transfer,)).start()
            return Response({
                "message": "Paiement réussi ! Crédit en cours...",
                "status": "debited"
            })

        # 3. MTN : paiement silencieux → pas de débit immédiat, on attend confirmation
        elif transfer.from_wallet == 'mtn-ci':
            transfer.status = 'pending_mtn'  # ← Nouveau statut spécifique
            transfer.paydunya_payment_ref = response.get('transaction_id', '')
            transfer.save()
            
            # Lance polling spécifique pour MTN (similaire à Wave)
            Thread(target=_poll_mtn_payment, args=(transfer,)).start()

            return Response({
                "message": "Paiement MTN en cours de validation automatique. Pas d’action requise.",
                "status": "pending_mtn"
            })

        else:
            return Response({"error": "Opérateur non supporté pour confirmation"}, status=400)



def _launch_credit(transfer):
    if transfer.status not in ['debited', 'pending_wave']:
        logger.info(f"Crédit ignoré – mauvais statut : {transfer.status}")
        return

    client = PayDunyaClient()
    # Suffix timestamp : idempotent au sein de cette tentative, unique entre retries
    disburse_id = f"MB{transfer.id}T{int(time.time())}"

    # 1. Création du déboursement — retry 3x sur timeout (disburse_id = clé idempotente)
    disburse = None
    for attempt in range(1, 4):
        try:
            disburse = client.disburse_create(
                phone=transfer.to_phone,
                amount=int(transfer.amount_sent),
                mode=transfer.to_wallet,
                callback_url="https://buudi.africa/api/v1/webhook-paydunya",
                disburse_id=disburse_id
            )
            break
        except requests.exceptions.Timeout:
            logger.warning(f"TIMEOUT disburse_create tentative {attempt}/3 → {disburse_id}")
            if attempt < 3:
                time.sleep(5 * attempt)
            else:
                # L'user est débité mais le crédit n'a pas pu être lancé → retryable
                transfer.status = 'credit_failed'
                transfer.save()
                logger.error(f"TIMEOUT DÉFINITIF disburse_create → {disburse_id} → statut: credit_failed")
                return
        except Exception as e:
            transfer.status = 'credit_failed'
            transfer.save()
            logger.error(f"ERREUR disburse_create → {disburse_id} → {e}", exc_info=True)
            return

    if disburse.get('response_code') != '00':
        transfer.status = 'credit_failed'
        transfer.save()
        logger.error(f"ÉCHEC disburse_create → {disburse}")
        return

    # 2. Soumission
    try:
        submit = client.disburse_submit(disburse['disburse_token'], disburse_id)
    except requests.exceptions.Timeout:
        # Le disburse existe côté PayDunya — on sauvegarde le token pour suivi
        transfer.disburse_token = disburse['disburse_token']
        transfer.disburse_id = disburse_id
        transfer.status = 'credit_failed'
        transfer.save()
        logger.error(f"TIMEOUT disburse_submit → {disburse_id} → token sauvegardé, statut: credit_failed")
        return
    except Exception as e:
        transfer.status = 'credit_failed'
        transfer.save()
        logger.error(f"ERREUR disburse_submit → {disburse_id} → {e}", exc_info=True)
        return

    if submit.get('response_code') != '00':
        transfer.status = 'credit_failed'
        transfer.save()
        logger.error(f"ÉCHEC disburse_submit → {submit}")
        return

    # 3. Token sauvegardé → passage en disbursing
    transfer.disburse_token = disburse['disburse_token']
    transfer.disburse_id = disburse_id
    transfer.status = 'disbursing'
    transfer.save()
    logger.info(f"CRÉDIT LANCÉ → {disburse_id} | Token: {disburse['disburse_token'][-10:]}... | Polling en cours...")

    # 4. Polling confirmation (20 × 3s = 60s)
    for attempt in range(20):
        time.sleep(3)
        check = client.check_status(disburse['disburse_token'])
        logger.info(f"Check status tentative {attempt + 1}/20 → {check}")

        if check.get('response_code') == '00':
            real_status = check.get('status')
            if real_status == 'success':
                transfer.status = 'success'
                transfer.save()
                logger.info(f"SUCCÈS CONFIRMÉ PAR POLLING → {disburse_id}")
                return
            elif real_status == 'failed':
                transfer.status = 'credit_failed'
                transfer.save()
                logger.error(f"ÉCHEC CONFIRMÉ PAR POLLING → {disburse_id}")
                return

    logger.warning(f"Timeout polling – statut reste 'disbursing' pour {disburse_id} (webhook attendu)")        
        
        
        
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
    
    
    
    
    
def _poll_mtn_payment(transfer):
    """
    Polling spécifique pour MTN CI : attend la confirmation du paiement silencieux.
    Similaire à _poll_wave_payment mais adapté à MTN (pas de redirection, pas d'URL).
    """
    client = PayDunyaClient()
    token = transfer.paydunya_invoice_token
    max_attempts = 40  # 40 × 4 sec = ~2 min 40 s max (comme Wave)

    for attempt in range(max_attempts):
        time.sleep(4)  # même délai que Wave

        status_check = client.check_invoice_status(token)
        logger.info(f"Polling MTN paiement tentative {attempt + 1} → {status_check.get('status')}")

        if status_check.get('status') == 'completed':
            logger.info(f"MTN PAIEMENT CONFIRMÉ PAR POLLING → Lancement crédit pour MB{transfer.id}")
            _launch_credit(transfer)  # réutilise ta fonction existante
            transfer.status = 'debited'  # ou 'success' selon ton modèle
            transfer.save()
            return

        elif status_check.get('status') in ['cancelled', 'failed', 'expired']:
            transfer.status = 'failed'
            transfer.save()
            logger.warning(f"MTN PAIEMENT ANNULÉ/ÉCHEC → MB{transfer.id}")
            return

        

    # Timeout : après ~2min40, on considère ça comme échoué
    transfer.status = 'failed'
    transfer.save()
    logger.warning(f"Timeout polling MTN – paiement non confirmé pour MB{transfer.id}")        
        
        
        




class TransferStatusView(APIView):
    def get(self, request, transfer_id):
        try:
            transfer = Transfer.objects.get(id=transfer_id)

            # Live check PayDunya quand le crédit est en cours —
            # chaque poll Flutter devient une vérification active (ex: payout Wave lent)
            if transfer.status == 'disbursing' and transfer.disburse_token:
                try:
                    client = PayDunyaClient()
                    check = client.check_status(transfer.disburse_token)
                    if check.get('response_code') == '00':
                        real_status = check.get('status')
                        if real_status == 'success':
                            transfer.status = 'success'
                            transfer.save()
                            logger.info(f"LIVE CHECK → SUCCÈS → MB{transfer.id}")
                        elif real_status == 'failed':
                            transfer.status = 'credit_failed'
                            transfer.save()
                            logger.error(f"LIVE CHECK → ÉCHEC CRÉDIT → MB{transfer.id}")
                except Exception as e:
                    logger.warning(f"Live check échoué MB{transfer.id}: {e}")

            is_final = transfer.status in ['success', 'failed', 'credit_failed']

            return Response({
                "status": transfer.status,
                "message": "Transfert terminé" if is_final else "En cours...",
                "final": is_final
            })

        except Transfer.DoesNotExist:
            return Response({"error": "Transfert non trouvé"}, status=404)      
        
        
        
        


class FeesConfigView(APIView):
    def get(self, request):
        fees = OperatorFees.objects.all().values(
            'operator',
            'payin_fee_percent',
            'payout_fee_percent'
        )
        
        # On transforme en dict facile à utiliser côté Flutter
        config = {
            "buudi_commission_percent": 1.5,  # Tu peux le mettre dans un modèle aussi
            "operators": {}
        }
        
        for fee in fees:
            op = fee['operator']
            config["operators"][op] = {
                "payin_percent": float(fee['payin_fee_percent']),
                "payout_percent": float(fee['payout_fee_percent'])
            }
        
        return Response(config)       
        
        
        
        
        
        
        
        
        
        
        
class CreditReceiverView(APIView):
    """Retry manuel du crédit pour les transferts bloqués (debited / credit_failed)."""
    throttle_classes = [CreditThrottle]

    def post(self, request):
        transfer_id = request.data.get('transfer_id')
        try:
            transfer = Transfer.objects.get(id=transfer_id)
        except Transfer.DoesNotExist:
            return Response({"error": "Transfert non trouvé"}, status=404)

        if transfer.status not in ['debited', 'credit_failed', 'disbursing']:
            return Response({
                "error": f"Statut '{transfer.status}' non retryable",
                "hint": "Seuls debited / credit_failed / disbursing peuvent être relancés"
            }, status=400)

        # Reset pour permettre le retry dans _launch_credit
        transfer.status = 'debited'
        transfer.save()

        Thread(target=_launch_credit, args=(transfer,)).start()
        return Response({
            "message": "Retry crédit lancé en arrière-plan",
            "transfer_id": transfer.id,
            "disburse_id": f"MB{transfer.id}"
        })


# ─────────────────────────────────────────────────────────────────────────────
# WEBHOOK PAYDUNYA — callback automatique quand un déboursement est confirmé
# ─────────────────────────────────────────────────────────────────────────────
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def paydunya_webhook(request):
    """
    Reçoit les notifications push de Paydunya pour les déboursements (payout).

    Payload disburse callback :
    {
        "status": "success" | "failed" | "pending",
        "token": "<disburse_token>",
        "disburse_id": "MB170T..." | "ADMIN5",
        "transaction_id": "TFA-TX-...",
        "withdraw_mode": "mtn-ci",
        "amount": "5000.00"
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    logger.info(f"WEBHOOK PAYDUNYA reçu → {payload}")

    status         = payload.get('status', '')
    disburse_id    = payload.get('disburse_id', '')
    token          = payload.get('token', '')
    transaction_id = payload.get('transaction_id', '')

    if not status:
        return JsonResponse({'received': True, 'note': 'no status'})

    # ── 1. ManualDisbursement (disburse_id = "ADMIN<id>") ────────────────────
    if disburse_id.startswith('ADMIN'):
        try:
            from dashboard_admin.models import ManualDisbursement
            md_id    = int(disburse_id.replace('ADMIN', '').split('T')[0])
            disburse = ManualDisbursement.objects.get(id=md_id)
            if status == 'success':
                disburse.status = 'success'
                if disburse.transfer and disburse.transfer.status != 'success':
                    disburse.transfer.status = 'success'
                    disburse.transfer.save(update_fields=['status'])
            elif status == 'failed':
                disburse.status = 'failed'
            disburse.paydunya_status = status
            disburse.transaction_id  = transaction_id or disburse.transaction_id
            disburse.paydunya_desc   = str(payload)
            disburse.save()
            logger.info(f"WEBHOOK → ManualDisbursement ADMIN#{md_id} → {status}")
        except Exception as e:
            logger.error(f"WEBHOOK → Erreur ManualDisbursement {disburse_id} : {e}")

    # ── 2. Transfer régulier (disburse_id = "MB<id>T<timestamp>") ────────────
    elif disburse_id.startswith('MB'):
        try:
            transfer_id = int(disburse_id.split('T')[0].replace('MB', ''))
            transfer    = Transfer.objects.get(id=transfer_id)
            if status == 'success' and transfer.status in ('disbursing', 'debited', 'credit_failed'):
                transfer.status = 'success'
                transfer.save(update_fields=['status'])
                logger.info(f"WEBHOOK → Transfer #{transfer_id} → SUCCESS")
            elif status == 'failed' and transfer.status in ('disbursing', 'debited', 'credit_failed'):
                transfer.status = 'credit_failed'
                transfer.save(update_fields=['status'])
                logger.error(f"WEBHOOK → Transfer #{transfer_id} → CREDIT_FAILED")
        except Exception as e:
            logger.error(f"WEBHOOK → Erreur Transfer {disburse_id} : {e}")

    # ── 3. Fallback : pas de disburse_id, recherche par token ────────────────
    elif token:
        try:
            transfer = Transfer.objects.get(disburse_token=token)
            if status == 'success' and transfer.status in ('disbursing', 'debited', 'credit_failed'):
                transfer.status = 'success'
                transfer.save(update_fields=['status'])
            elif status == 'failed' and transfer.status in ('disbursing', 'debited'):
                transfer.status = 'credit_failed'
                transfer.save(update_fields=['status'])
        except Transfer.DoesNotExist:
            try:
                from dashboard_admin.models import ManualDisbursement
                md = ManualDisbursement.objects.get(disburse_token=token)
                md.status          = 'success' if status == 'success' else ('failed' if status == 'failed' else 'pending')
                md.paydunya_status = status
                md.transaction_id  = transaction_id or md.transaction_id
                md.save()
            except Exception:
                logger.warning(f"WEBHOOK → token {token[:15]}... introuvable")
        except Exception as e:
            logger.error(f"WEBHOOK → Erreur fallback token : {e}")

    return JsonResponse({'received': True})
















class UserTransactionsView(APIView):
    def get(self, request):
        phone = request.headers.get('X-User-Phone')
        if not phone:
            return Response({"error": "X-User-Phone requis"}, status=400)

        try:
            user = UserProfile.objects.get(phone=phone)
        except UserProfile.DoesNotExist:
            return Response({"error": "Utilisateur inconnu"}, status=404)

        # Get all transactions for the user, ordered by recent first
        transfers = Transfer.objects.filter(user=user).order_by('-created_at')

        # Serialize and return
        serializer = TransferSerializer(transfers, many=True)
        return Response(serializer.data)