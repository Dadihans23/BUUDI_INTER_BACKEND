from django.shortcuts import render
# Python standard
import csv
import json
import random
import secrets
import string
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from functools import wraps
from io import StringIO, BytesIO
from threading import Thread

# Django
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import (
    Sum,
    Count,
    F,
    Q,
    ExpressionWrapper,
    DecimalField,
)
from django.utils import timezone


def api_rate_limit(calls, period, scope='api'):
    """
    Décorateur rate-limit basé sur Django cache (LocMemCache).
    calls  : nombre max de requêtes autorisées
    period : fenêtre en secondes
    scope  : préfixe de la clé cache
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            ip  = (request.META.get('HTTP_X_FORWARDED_FOR', '') or
                   request.META.get('REMOTE_ADDR', 'unknown')).split(',')[0].strip()
            key = f"rl:{scope}:{ip}"
            count = cache.get(key, 0)
            if count >= calls:
                return JsonResponse({
                    'error': f'Trop de requêtes. Réessayez dans {period} secondes.',
                    'retry_after': period,
                }, status=429)
            cache.set(key, count + 1, period)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator

# Apps du projet
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from transfers.models import Transfer, OperatorFees
from transfers.views import _launch_credit
from users.models import UserProfile


def _log(request, action, summary, obj_type='', obj_id=None):
    """Enregistre une action admin dans le journal d'audit."""
    from dashboard_admin.models import AuditLog
    ip = (request.META.get('HTTP_X_FORWARDED_FOR', '') or
          request.META.get('REMOTE_ADDR', '')).split(',')[0].strip() or None
    try:
        AuditLog.objects.create(
            admin=request.user if request.user.is_authenticated else None,
            action=action,
            object_type=obj_type,
            object_id=obj_id,
            summary=summary,
            ip_address=ip,
        )
    except Exception:
        pass  # ne jamais bloquer une action admin à cause du log

# =====================================
# DASHBOARD
# =====================================@login_required
def admin_dashboard(request):
    # Filtres date
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    transfers = Transfer.objects.all().order_by('-created_at')
    
    if from_date:
        transfers = transfers.filter(created_at__gte=from_date)
    if to_date:
        transfers = transfers.filter(created_at__lte=to_date)

    # Stats globales
    total_users = UserProfile.objects.count()
    total_transfers = transfers.count()
    transfers_today = transfers.filter(created_at__date=date.today()).count()
    successful_transfers = transfers.filter(status='success').count()
    pending_transfers = transfers.filter(status__in=['created', 'invoice_sent', 'debited', 'disbursing']).count()
    failed_transfers = transfers.filter(status='failed').count()

    # Revenus (nos bénéfices = our_fee_amount)
    our_revenue = transfers.filter(status='success').aggregate(total=Sum('our_fee_amount'))['total'] or Decimal('0.00')

    # Frais payés à Paydunia (payin + payout)
    paydunia_fees = transfers.filter(status='success').aggregate(
        total=Sum(F('payin_fee_amount') + F('payout_fee_amount'), output_field=DecimalField())
    )['total'] or Decimal('0.00')

    # Montant total transféré
    total_volume = transfers.filter(status='success').aggregate(total=Sum('amount_sent'))['total'] or Decimal('0.00')

    # Stats supplémentaires pertinentes
    average_transfer = total_volume / successful_transfers if successful_transfers else Decimal('0.00')
    success_rate = (successful_transfers / total_transfers * 100) if total_transfers else 0

    # Top opérateurs
    top_from = transfers.values('from_wallet').annotate(count=Count('id'), volume=Sum('amount_sent')).order_by('-volume')[:5]
    top_to = transfers.values('to_wallet').annotate(count=Count('id'), volume=Sum('amount_sent')).order_by('-volume')[:5]

    context = {
        'total_users': total_users,
        'total_transfers': total_transfers,
        'transfers_today': transfers_today,
        'successful_transfers': successful_transfers,
        'pending_transfers': pending_transfers,
        'failed_transfers': failed_transfers,
        'our_revenue': our_revenue,
        'paydunia_fees': paydunia_fees,
        'total_volume': total_volume,
        'average_transfer': average_transfer,
        'success_rate': success_rate,
        'top_from': top_from,
        'top_to': top_to,
        'from_date': from_date,
        'to_date': to_date,
    }
    return render(request, 'custom_admin/admin/dashboard.html', context)
# =====================================
# UTILISATEURS
# =====================================
@login_required
def admin_users(request):
    users = UserProfile.objects.all().order_by('-created_at')
    search = request.GET.get('search', '').strip()
    if search:
        users = users.filter(Q(name__icontains=search) | Q(phone__icontains=search))
    paginator = Paginator(users, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total_users = UserProfile.objects.count()
    new_this_month = UserProfile.objects.filter(created_at__gte=month_start).count()
    active_users = UserProfile.objects.filter(transfer__isnull=False).distinct().count()

    return render(request, 'custom_admin/admin/users.html', {
        'page_obj': page_obj,
        'search_query': search,
        'total_users': total_users,
        'new_this_month': new_this_month,
        'active_users': active_users,
    })

@login_required
def admin_user_detail(request, user_id):
    user = get_object_or_404(UserProfile, id=user_id)
    transfers = user.transfer_set.all().order_by('-created_at')[:20]
    return render(request, 'custom_admin/admin/user_detail.html', {'user': user, 'transfers': transfers})

@login_required
def admin_user_edit(request, user_id):
    user = get_object_or_404(UserProfile, id=user_id)
    if request.method == 'POST':
        old_name  = user.name
        old_phone = user.phone
        user.name  = request.POST.get('name')
        user.phone = request.POST.get('phone')
        user.save()
        _log(request, 'user_edit',
             f"User #{user_id}: nom {old_name}→{user.name}, tél {old_phone}→{user.phone}",
             'UserProfile', user_id)
        messages.success(request, f"Utilisateur {user.name} modifié avec succès !")
        return redirect('custom_admin:user_detail', user_id=user.id)
    return render(request, 'custom_admin/admin/user_edit.html', {'user': user})

# @login_required
# def admin_user_delete(request, user_id):
#     user = get_object_or_404(UserProfile, id=user_id)
#     if request.method == 'POST':
#         user.delete()
#         messages.success(request, f"Utilisateur {user.name} supprimé !")
#         return redirect('custom_admin:users')
#     return redirect('custom_admin:users')

@login_required
def admin_user_create(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        name = request.POST.get('name')
        if UserProfile.objects.filter(phone=phone).exists():
            messages.error(request, "Ce numéro existe déjà.")
        else:
            u = UserProfile.objects.create(phone=phone, name=name)
            _log(request, 'user_create', f"User {name} ({phone}) créé", 'UserProfile', u.id)
            messages.success(request, f"Utilisateur {name} créé !")
            return redirect('custom_admin:users')
    return render(request, 'custom_admin/admin/user_create.html')


# =====================================
# TRANSFERTS
# =====================================
@login_required
def admin_transfers(request):
    transfers = Transfer.objects.select_related('user').order_by('-created_at')

    # Filtres
    status = request.GET.get('status')
    operator = request.GET.get('operator')
    search = request.GET.get('search')

    if status:
        transfers = transfers.filter(status=status)
    if operator:
        transfers = transfers.filter(Q(from_wallet__icontains=operator) | Q(to_wallet__icontains=operator))
    if search:
        transfers = transfers.filter(
            Q(user__phone__icontains=search) |
            Q(from_phone__icontains=search) |
            Q(to_phone__icontains=search)
        )

    paginator = Paginator(transfers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_filter': status,
        'operator_filter': operator,
        'search_query': search,
    }
    return render(request, 'custom_admin/admin/transfers.html', context)

@login_required
def admin_transfer_detail(request, transfer_id):
    transfer = get_object_or_404(Transfer, id=transfer_id)
    return render(request, 'custom_admin/admin/transfer_detail.html', {'transfer': transfer})

@login_required
def admin_transfer_edit(request, transfer_id):
    transfer = get_object_or_404(Transfer, id=transfer_id)
    if request.method == 'POST':
        old_status = transfer.status
        transfer.status = request.POST.get('status', transfer.status)
        transfer.save()
        _log(request, 'transfer_edit',
             f"Transfer #{transfer_id}: statut {old_status}→{transfer.status}",
             'Transfer', transfer_id)
        messages.success(request, "Transfert mis à jour !")
        return redirect('custom_admin:transfer_detail', transfer_id=transfer.id)
    return render(request, 'custom_admin/admin/transfer_edit.html', {'transfer': transfer})

@login_required
def admin_transfer_delete(request, transfer_id):
    transfer = get_object_or_404(Transfer, id=transfer_id)
    if request.method == 'POST':
        _log(request, 'transfer_delete',
             f"Transfer #{transfer_id} ({transfer.status}) {transfer.amount_requested}F "
             f"{transfer.from_wallet}→{transfer.to_wallet} supprimé",
             'Transfer', transfer_id)
        transfer.delete()
        messages.success(request, "Transfert supprimé !")
        return redirect('custom_admin:transfers')
    return redirect('custom_admin:transfers')

@login_required
def admin_transfer_retry(request, transfer_id):
    transfer = get_object_or_404(Transfer, id=transfer_id)
    if transfer.status == 'failed':
        transfer.status = 'created'
        transfer.save()
        _log(request, 'transfer_retry', f"Transfer #{transfer_id} remis en file (failed→created)",
             'Transfer', transfer_id)
        messages.success(request, "Transfert remis en file d'attente pour réessai.")
    return redirect('custom_admin:transfer_detail', transfer_id=transfer.id)

@login_required
def admin_credit_retry(request, transfer_id):
    """Relance le crédit (envoi vers le destinataire) pour un transfert bloqué."""
    transfer = get_object_or_404(Transfer, id=transfer_id)

    if transfer.status not in ['credit_failed', 'debited', 'disbursing']:
        messages.error(request, f"Impossible de relancer le crédit : statut '{transfer.get_status_display()}' non éligible.")
        return redirect('custom_admin:transfer_detail', transfer_id=transfer.id)

    transfer.status = 'debited'
    transfer.save()
    Thread(target=_launch_credit, args=(transfer,)).start()
    _log(request, 'credit_retry',
         f"Credit retry #{transfer.id}: {transfer.amount_requested}F → {transfer.to_phone} ({transfer.to_wallet})",
         'Transfer', transfer.id)

    messages.success(
        request,
        f"Crédit relancé pour le transfert #{transfer.id} — "
        f"{transfer.amount_requested} FCFA vers {transfer.to_phone} ({transfer.to_wallet})."
    )
    # Retourner à la liste re-crédit si on vient de là, sinon au détail
    referer = request.META.get('HTTP_REFERER', '')
    if 'recredits' in referer:
        return redirect('custom_admin:recredits')
    return redirect('custom_admin:transfer_detail', transfer_id=transfer.id)


# ─── RE-CRÉDIT : transferts débités mais non crédités ──────────────────────
@login_required
def admin_recredits(request):
    """Liste tous les transferts où l'utilisateur a été débité mais le crédit a échoué."""
    from django.utils import timezone
    from datetime import timedelta

    # Statut credit_failed : débité + crédit définitivement échoué
    credit_failed = Transfer.objects.filter(status='credit_failed').order_by('-updated_at')

    # Statut debited bloqué depuis plus de 10 min (thread tombé sans changer le statut)
    stuck_threshold = timezone.now() - timedelta(minutes=10)
    stuck_debited = Transfer.objects.filter(
        status='debited',
        updated_at__lt=stuck_threshold
    ).order_by('-updated_at')

    total_pending = credit_failed.count() + stuck_debited.count()

    # Relance groupée : tous les credit_failed d'un coup
    if request.method == 'POST' and request.POST.get('action') == 'retry_all':
        relaunched = 0
        for t in credit_failed:
            t.status = 'debited'
            t.save()
            Thread(target=_launch_credit, args=(t,)).start()
            relaunched += 1
        for t in stuck_debited:
            Thread(target=_launch_credit, args=(t,)).start()
            relaunched += 1
        _log(request, 'credit_retry_all', f"{relaunched} crédit(s) relancé(s) en masse")
        messages.success(request, f"{relaunched} crédit(s) relancé(s) en arrière-plan.")
        return redirect('custom_admin:recredits')

    return render(request, 'custom_admin/admin/recredits.html', {
        'credit_failed': credit_failed,
        'stuck_debited': stuck_debited,
        'total_pending': total_pending,
    })


# =====================================
# RÉCONCILIATION DISBURSING
# =====================================
@login_required
def admin_reconcile(request):
    """
    POST → vérifie tous les transferts 'disbursing' depuis > 1h via check_status Paydunya
    et met à jour leur statut.  Retourne JSON pour AJAX.
    """
    from paydunya.client import PayDunyaClient

    seuil = timezone.now() - timedelta(hours=1)
    bloqués = Transfer.objects.filter(status='disbursing', updated_at__lt=seuil)
    total = bloqués.count()

    if total == 0:
        return JsonResponse({'total': 0, 'success': 0, 'failed': 0, 'pending': 0,
                             'message': 'Aucun transfert bloqué.'})

    client  = PayDunyaClient()
    success = failed = pending = 0

    for t in bloqués:
        if not t.disburse_token:
            pending += 1
            continue
        try:
            check = client.check_status(t.disburse_token)
            if check.get('response_code') != '00':
                pending += 1
                continue
            raw = check.get('status', 'pending')
            if raw == 'success':
                t.status = 'success'
                t.save(update_fields=['status'])
                success += 1
            elif raw == 'failed':
                t.status = 'credit_failed'
                t.save(update_fields=['status'])
                failed += 1
            elif raw == 'created':
                try:
                    client.disburse_submit(t.disburse_token, t.disburse_id)
                except Exception:
                    pass
                pending += 1
            else:
                pending += 1
        except Exception:
            pending += 1

    _log(request, 'reconcile',
         f"{total} vérifiés: {success} réussis, {failed} échoués, {pending} en attente")
    return JsonResponse({
        'total':   total,
        'success': success,
        'failed':  failed,
        'pending': pending,
        'message': f'{success} réussis, {failed} échoués, {pending} encore en attente.',
    })


# =====================================
# FRAIS OPÉRATEURS
# =====================================
@login_required
def admin_operator_fees(request):
    fees = OperatorFees.objects.all()
    return render(request, 'custom_admin/admin/fees.html', {'fees': fees})

@login_required
def admin_edit_operator_fee(request, operator):
    fee = get_object_or_404(OperatorFees, operator=operator)
    if request.method == 'POST':
        old_payin  = fee.payin_fee_percent
        old_payout = fee.payout_fee_percent
        fee.payin_fee_percent  = Decimal(request.POST.get('payin_fee_percent'))
        fee.payout_fee_percent = Decimal(request.POST.get('payout_fee_percent'))
        fee.save()
        _log(request, 'fee_edit',
             f"{operator.upper()}: payin {old_payin}%→{fee.payin_fee_percent}%, "
             f"payout {old_payout}%→{fee.payout_fee_percent}%",
             'OperatorFees')
        messages.success(request, f"Frais pour {operator.upper()} mis à jour !")
        return redirect('custom_admin:fees')
    return render(request, 'custom_admin/admin/edit_fee.html', {'fee': fee})


# =====================================
# PARAMÈTRES
# =====================================
@login_required
def admin_settings(request):
    if request.method == 'POST':
        # Ici tu peux ajouter des paramètres globaux (ex: ta marge par défaut)
        messages.success(request, "Paramètres sauvegardés !")
        return redirect('custom_admin:settings')
    return render(request, 'custom_admin/admin/settings.html')


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay, TruncHour
from decimal import Decimal




@login_required
def admin_revenue_analytics(request):
    # Filtres période
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    transfers = Transfer.objects.filter(status='success')
    
    if from_date:
        transfers = transfers.filter(created_at__gte=from_date)
    if to_date:
        transfers = transfers.filter(created_at__lte=to_date + ' 23:59:59')

    # Revenue total (notre marge)
    total_revenue = transfers.aggregate(total=Sum('our_fee_amount'))['total'] or Decimal('0.00')

    # Revenue par opérateur payin
    revenue_by_payin = transfers.values('from_wallet')\
        .annotate(revenue=Sum('our_fee_amount'))\
        .order_by('-revenue')

    # Revenue par opérateur payout
    revenue_by_payout = transfers.values('to_wallet')\
        .annotate(revenue=Sum('our_fee_amount'))\
        .order_by('-revenue')

    # Usage par opérateur
    usage_payin = transfers.values('from_wallet').annotate(count=Count('id'))
    usage_payout = transfers.values('to_wallet').annotate(count=Count('id'))

    # Affluences
    affluence_day = transfers.annotate(day=TruncDay('created_at'))\
        .values('day')\
        .annotate(count=Count('id'))\
        .order_by('day')

    affluence_hour = transfers.annotate(hour=TruncHour('created_at'))\
        .values('hour')\
        .annotate(count=Count('id'))\
        .order_by('hour')

    # Autres stats pertinentes
    total_volume = transfers.aggregate(total=Sum('amount_sent'))['total'] or Decimal('0.00')
    average_revenue_per_transfer = total_revenue / transfers.count() if transfers.count() > 0 else Decimal('0.00')
    failure_rate = (Transfer.objects.filter(status='failed').count() / Transfer.objects.count() * 100) if Transfer.objects.count() > 0 else 0
    peak_day = affluence_day.order_by('-count').first() if affluence_day else None
    peak_hour = affluence_hour.order_by('-count').first() if affluence_hour else None

    context = {
        'total_revenue': total_revenue,
        'revenue_by_payin': revenue_by_payin,
        'revenue_by_payout': revenue_by_payout,
        'usage_payin': usage_payin,
        'usage_payout': usage_payout,
        'affluence_day': affluence_day,
        'affluence_hour': affluence_hour,
        'total_volume': total_volume,
        'average_revenue_per_transfer': average_revenue_per_transfer,
        'failure_rate': failure_rate,
        'peak_day': peak_day,
        'peak_hour': peak_hour,
        'from_date': from_date,
        'to_date': to_date,
    }
    return render(request, 'custom_admin/admin/revenue_analytics.html', context)




from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User  # Utilise le User Django standard
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import SupportTicket, SupportMessage, ManualDisbursement


# =====================================
# SUPPORT — API MOBILE (JSON)
# =====================================

@csrf_exempt
@api_rate_limit(calls=20, period=3600, scope='support_create')
def api_support_list_create(request):
    """
    GET  ?phone=  → liste les tickets du user
    POST body {phone, category, subject, first_message} → crée un ticket
    """
    if request.method == 'GET':
        phone = request.GET.get('phone', '').strip()
        if not phone:
            return JsonResponse({'error': 'phone requis'}, status=400)
        try:
            user = UserProfile.objects.get(phone=phone)
        except UserProfile.DoesNotExist:
            return JsonResponse({'tickets': []})
        tickets = SupportTicket.objects.filter(user=user).values(
            'id', 'category', 'subject', 'status', 'created_at', 'updated_at'
        )
        data = []
        for t in tickets:
            data.append({
                'id': t['id'],
                'category': t['category'],
                'subject': t['subject'],
                'status': t['status'],
                'created_at': t['created_at'].isoformat(),
                'updated_at': t['updated_at'].isoformat(),
            })
        return JsonResponse({'tickets': data})

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        phone = body.get('phone', '').strip()
        category = body.get('category', '').strip()
        subject = body.get('subject', '').strip()
        first_message = body.get('first_message', '').strip()

        if not all([phone, category, subject, first_message]):
            return JsonResponse({'error': 'phone, category, subject et first_message requis'}, status=400)

        try:
            user = UserProfile.objects.get(phone=phone)
        except UserProfile.DoesNotExist:
            return JsonResponse({'error': 'Utilisateur introuvable'}, status=404)

        ticket = SupportTicket.objects.create(user=user, category=category, subject=subject)
        SupportMessage.objects.create(ticket=ticket, sender='user', content=first_message)

        return JsonResponse({
            'ticket': {
                'id': ticket.id,
                'category': ticket.category,
                'subject': ticket.subject,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
            }
        }, status=201)

    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@csrf_exempt
def api_support_detail(request, ticket_id):
    """GET ?phone= → détail ticket + messages"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    phone = request.GET.get('phone', '').strip()
    if not phone:
        return JsonResponse({'error': 'phone requis'}, status=400)

    try:
        ticket = SupportTicket.objects.get(id=ticket_id, user__phone=phone)
    except SupportTicket.DoesNotExist:
        return JsonResponse({'error': 'Ticket introuvable'}, status=404)

    messages_data = [
        {
            'id': m.id,
            'sender': m.sender,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
        }
        for m in ticket.messages.all()
    ]

    return JsonResponse({
        'ticket': {
            'id': ticket.id,
            'category': ticket.category,
            'subject': ticket.subject,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat(),
        },
        'messages': messages_data,
    })


@csrf_exempt
@api_rate_limit(calls=30, period=3600, scope='support_reply')
def api_support_user_reply(request, ticket_id):
    """POST body {phone, content} → ajoute un message user"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    phone = body.get('phone', '').strip()
    content = body.get('content', '').strip()

    if not all([phone, content]):
        return JsonResponse({'error': 'phone et content requis'}, status=400)

    try:
        ticket = SupportTicket.objects.get(id=ticket_id, user__phone=phone)
    except SupportTicket.DoesNotExist:
        return JsonResponse({'error': 'Ticket introuvable'}, status=404)

    if ticket.status == 'resolved':
        return JsonResponse({'error': 'Ce ticket est résolu'}, status=400)

    # Repasser en in_progress si c'était résolu ou open
    if ticket.status == 'open':
        ticket.status = 'in_progress'
        ticket.save()

    msg = SupportMessage.objects.create(ticket=ticket, sender='user', content=content)

    return JsonResponse({
        'message': {
            'id': msg.id,
            'sender': msg.sender,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
        }
    }, status=201)


# =====================================
# SUPPORT — DASHBOARD HTML (admin)
# =====================================

@login_required
def admin_support_list(request):
    status_filter = request.GET.get('status', '')
    tickets = SupportTicket.objects.select_related('user').all()
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    paginator = Paginator(tickets, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    open_count = SupportTicket.objects.filter(status='open').count()
    return render(request, 'custom_admin/admin/support_list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'open_count': open_count,
    })


@login_required
def admin_support_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    support_messages = ticket.messages.all()
    return render(request, 'custom_admin/admin/support_detail.html', {
        'ticket': ticket,
        'support_messages': support_messages,
    })


@login_required
def admin_support_reply(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            SupportMessage.objects.create(ticket=ticket, sender='support', content=content)
            ticket.status = 'in_progress'
            ticket.save()
            _log(request, 'support_reply',
                 f"Ticket #{ticket_id} [{ticket.subject[:40]}]: réponse ajoutée",
                 'SupportTicket', ticket_id)
            messages.success(request, 'Réponse envoyée.')
        else:
            messages.error(request, 'Le message ne peut pas être vide.')
    return redirect('custom_admin:support_detail', ticket_id=ticket_id)


@login_required
def admin_support_resolve(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == 'POST':
        ticket.status = 'resolved'
        ticket.save()
        _log(request, 'support_resolve',
             f"Ticket #{ticket_id} [{ticket.subject[:40]}] marqué résolu",
             'SupportTicket', ticket_id)
        messages.success(request, 'Ticket marqué comme résolu.')
    return redirect('custom_admin:support_detail', ticket_id=ticket_id)


def admin_login(request):
    if request.user.is_authenticated:
        return redirect('custom_admin:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, "Veuillez remplir tous les champs.")
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if user.is_staff or user.is_superuser:  # Seul les admins accèdent
                    login(request, user)
                    return redirect('custom_admin:dashboard')
                else:
                    messages.error(request, "Vous n'avez pas les droits d'administrateur.")
            else:
                messages.error(request, "Identifiants incorrects.")

    return render(request, 'custom_admin/admin/login.html')

@login_required
def admin_logout(request):
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('custom_admin:login')

# ─── LANDING PAGE ────────────────────────────────────────────────────────────
def landing_page(request):
    return render(request, 'landing.html')


# =====================================
# DÉBOURSEMENT DIRECT (ADMIN)
# =====================================

# Tous les withdraw_mode supportés par Paydunya
DISBURSE_OPERATORS = [
    ('wave-ci',               '🇨🇮 Wave CI'),
    ('orange-money-ci',       '🇨🇮 Orange Money CI'),
    ('mtn-ci',                '🇨🇮 MTN CI'),
    ('moov-ci',               '🇨🇮 Moov CI'),
    ('wave-senegal',          '🇸🇳 Wave Sénégal'),
    ('orange-money-senegal',  '🇸🇳 Orange Money Sénégal'),
    ('free-money-senegal',    '🇸🇳 Free Money Sénégal'),
    ('expresso-senegal',      '🇸🇳 E-Money Sénégal'),
    ('mtn-benin',             '🇧🇯 MTN Bénin'),
    ('moov-benin',            '🇧🇯 Moov Bénin'),
    ('t-money-togo',          '🇹🇬 T-Money Togo'),
    ('moov-togo',             '🇹🇬 Moov Togo'),
    ('orange-money-mali',     '🇲🇱 Orange Money Mali'),
    ('orange-money-burkina',  '🇧🇫 Orange Money Burkina'),
    ('moov-burkina-faso',     '🇧🇫 Moov Burkina'),
]


@login_required
def admin_manual_disburse(request):
    """
    GET  → affiche le formulaire + historique des déboursements manuels.
    POST → crée et soumet un déboursement direct via l'API Paydunya.
    """
    from paydunya.client import PayDunyaClient
    import time as _time

    if request.method == 'POST':
        phone    = request.POST.get('phone', '').strip()
        amount   = request.POST.get('amount', '').strip()
        operator = request.POST.get('operator', '').strip()
        notes    = request.POST.get('notes', '').strip()
        transfer_id = request.POST.get('transfer_id', '').strip()

        # ── Validation basique ──────────────────────────────────────────
        errors = []
        if not phone:
            errors.append("Le numéro de téléphone est requis.")
        if not amount or not amount.isdigit() or int(amount) <= 0:
            errors.append("Le montant doit être un entier positif.")
        if not operator:
            errors.append("L'opérateur est requis.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('custom_admin:manual_disburse')

        amount_int = int(amount)
        transfer_obj = None
        if transfer_id:
            try:
                from transfers.models import Transfer as T
                transfer_obj = T.objects.get(id=int(transfer_id))
            except Exception:
                pass

        # ── Créer l'enregistrement (statut pending) ─────────────────────
        disburse = ManualDisbursement.objects.create(
            admin=request.user,
            phone=phone,
            operator=operator,
            amount=amount_int,
            transfer=transfer_obj,
            notes=notes,
            status='pending',
        )
        ref_id = f"ADMIN{disburse.id}"
        disburse.disburse_ref_id = ref_id
        disburse.save(update_fields=['disburse_ref_id'])

        client = PayDunyaClient()

        # ── Étape 1 : get-invoice ────────────────────────────────────────
        try:
            get_resp = client.disburse_create(
                phone=phone,
                amount=amount_int,
                mode=operator,
                callback_url="https://buudi.africa/api/v1/webhook-paydunya",
                disburse_id=ref_id,
            )
        except Exception as exc:
            disburse.status = 'failed'
            disburse.paydunya_desc = f"Erreur réseau get-invoice : {exc}"
            disburse.save()
            messages.error(request, f"Impossible de joindre Paydunya : {exc}")
            return redirect('custom_admin:manual_disburse')

        if get_resp.get('response_code') != '00':
            disburse.status = 'failed'
            disburse.paydunya_desc = get_resp.get('response_text', str(get_resp))
            disburse.save()
            messages.error(
                request,
                f"Paydunya a refusé la demande : {get_resp.get('response_text', 'Erreur inconnue')}"
            )
            return redirect('custom_admin:manual_disburse')

        token = get_resp['disburse_token']
        disburse.disburse_token = token
        disburse.save(update_fields=['disburse_token'])

        # ── Étape 2 : submit-invoice ─────────────────────────────────────
        try:
            sub_resp = client.disburse_submit(token, ref_id)
        except Exception as exc:
            # Le token existe côté Paydunya : on laisse en pending pour vérification
            disburse.paydunya_desc = f"Timeout submit-invoice : {exc}"
            disburse.save()
            messages.warning(
                request,
                f"Déboursement ADMIN#{disburse.id} créé mais soumission timeout. "
                "Vérifiez le statut manuellement."
            )
            return redirect('custom_admin:manual_disburse')

        if sub_resp.get('response_code') == '00':
            raw_status = sub_resp.get('status', '')
            # Doc Paydunya : la plupart des wallets (Orange CI, MTN CI, Wave, Moov…)
            # retournent response_code '00' SANS champ 'status' → c'est un succès.
            # Seuls Free Money, Orange Mali/Burkina retournent status: 'pending'.
            if raw_status == 'pending':
                final_status = 'pending'
            elif raw_status == 'failed':
                final_status = 'failed'
            else:
                # 'success' explicite OU champ absent → succès confirmé
                final_status = 'success'
            disburse.status         = final_status
            disburse.paydunya_status = raw_status
            disburse.transaction_id  = sub_resp.get('transaction_id', '')
            disburse.provider_ref    = sub_resp.get('provider_ref', '')
            disburse.paydunya_desc   = sub_resp.get('description', '')
            disburse.save()

            if final_status == 'success':
                # Mettre à jour le transfert lié si présent
                if transfer_obj:
                    transfer_obj.status = 'success'
                    transfer_obj.save(update_fields=['status'])
                _log(request, 'manual_disburse',
                     f"ADMIN#{disburse.id}: {amount_int}F → {phone} ({operator}) → success",
                     'ManualDisbursement', disburse.id)
                messages.success(
                    request,
                    f"✅ Crédit envoyé avec succès ! ADMIN#{disburse.id} → "
                    f"{amount_int} F sur {phone} ({operator})."
                )
            elif final_status == 'pending':
                # Paydunya traite async : on attend 5s puis on re-vérifie directement
                import time as _t
                _t.sleep(5)
                try:
                    chk2 = client.check_status(token)
                    if chk2.get('response_code') == '00':
                        rs2 = chk2.get('status', 'pending')
                        if rs2 == 'created':
                            client.disburse_submit(token, ref_id)
                            _t.sleep(4)
                            chk2 = client.check_status(token)
                            rs2 = chk2.get('status', 'pending')
                        fs2 = 'success' if rs2 == 'success' else ('failed' if rs2 == 'failed' else 'pending')
                        disburse.status          = fs2
                        disburse.paydunya_status = rs2
                        disburse.transaction_id  = chk2.get('transaction_id', disburse.transaction_id)
                        disburse.paydunya_desc   = str(chk2)
                        disburse.save()
                        if fs2 == 'success':
                            if transfer_obj:
                                transfer_obj.status = 'success'
                                transfer_obj.save(update_fields=['status'])
                            _log(request, 'manual_disburse',
                                 f"ADMIN#{disburse.id}: {amount_int}F → {phone} ({operator}) → success (après attente)",
                                 'ManualDisbursement', disburse.id)
                            messages.success(
                                request,
                                f"✅ Crédit confirmé ! ADMIN#{disburse.id} → "
                                f"{amount_int} F sur {phone} ({operator})."
                            )
                            return redirect('custom_admin:manual_disburse')
                        elif fs2 == 'failed':
                            _log(request, 'manual_disburse',
                                 f"ADMIN#{disburse.id}: {amount_int}F → {phone} ({operator}) → failed",
                                 'ManualDisbursement', disburse.id)
                            messages.error(request, f"❌ Déboursement ADMIN#{disburse.id} échoué.")
                            return redirect('custom_admin:manual_disburse')
                except Exception:
                    pass
                # Toujours pending après vérification → bouton manuel
                messages.warning(
                    request,
                    f"⏳ Déboursement ADMIN#{disburse.id} toujours en attente. "
                    "Cliquez sur 'Vérifier' dans l'historique dans quelques secondes."
                )
            else:
                messages.error(
                    request,
                    f"❌ Déboursement ADMIN#{disburse.id} échoué : "
                    f"{sub_resp.get('response_text', 'Inconnu')}"
                )
        else:
            # response_code != 00 → on vérifie le statut réel
            try:
                check = client.check_status(token)
                raw_status = check.get('status', 'pending')
                final_check = 'success' if raw_status == 'success' else ('failed' if raw_status == 'failed' else 'pending')
                disburse.status          = final_check
                disburse.paydunya_status = raw_status
                disburse.transaction_id  = check.get('transaction_id', '')
                disburse.paydunya_desc   = str(check)
                disburse.save()
                if final_check == 'success' and disburse.transfer:
                    disburse.transfer.status = 'success'
                    disburse.transfer.save(update_fields=['status'])
            except Exception:
                disburse.status = 'pending'
                disburse.save()

            messages.warning(
                request,
                f"Réponse ambiguë de Paydunya (ADMIN#{disburse.id}). "
                f"Statut actuel : {disburse.status}. Vérifiez manuellement si nécessaire."
            )

        return redirect('custom_admin:manual_disburse')

    # ── GET : liste + formulaire ────────────────────────────────────────────
    history = ManualDisbursement.objects.select_related('admin', 'transfer').all()[:50]

    # Statistiques rapides
    stats = {
        'total':   ManualDisbursement.objects.count(),
        'success': ManualDisbursement.objects.filter(status='success').count(),
        'pending': ManualDisbursement.objects.filter(status='pending').count(),
        'failed':  ManualDisbursement.objects.filter(status='failed').count(),
        'volume':  ManualDisbursement.objects.filter(status='success').aggregate(
            v=Sum('amount'))['v'] or 0,
    }

    return render(request, 'custom_admin/admin/manual_disburse.html', {
        'operators': DISBURSE_OPERATORS,
        'history':   history,
        'stats':     stats,
    })


@login_required
def admin_check_disburse_status(request, disburse_id):
    """
    AJAX POST → interroge Paydunya pour mettre à jour le statut d'un
    déboursement manuel en attente (pending).
    Retourne JSON.
    """
    from paydunya.client import PayDunyaClient

    disburse = get_object_or_404(ManualDisbursement, id=disburse_id)

    if not disburse.disburse_token:
        return JsonResponse({'error': 'Aucun token disponible pour ce déboursement.'}, status=400)

    client = PayDunyaClient()
    try:
        check = client.check_status(disburse.disburse_token)
    except Exception as exc:
        return JsonResponse({'error': f'Erreur réseau : {exc}'}, status=500)

    # Doc Paydunya : response_code '00' = requête valide, sinon erreur
    if check.get('response_code') != '00':
        return JsonResponse({
            'error': check.get('response_text', 'Erreur Paydunya'),
            'raw':   check,
        }, status=400)

    # Statuts disbursement Paydunya : created, pending, success, failed
    raw_status = check.get('status', 'pending')

    if raw_status == 'created':
        # Le submit n'est pas passé — on re-soumet avec le même token
        try:
            client.disburse_submit(disburse.disburse_token, disburse.disburse_ref_id)
        except Exception:
            pass
        final = 'pending'  # sera confirmé au prochain check

    elif raw_status == 'success':
        final = 'success'
    elif raw_status == 'failed':
        final = 'failed'
    else:
        final = 'pending'  # pending ou inconnu

    old_status = disburse.status
    disburse.status          = final
    disburse.paydunya_status = raw_status
    disburse.transaction_id  = check.get('transaction_id', disburse.transaction_id)
    disburse.paydunya_desc   = str(check)
    disburse.save()

    if old_status != final:
        _log(request, 'disburse_check',
             f"ADMIN#{disburse.id}: statut {old_status}→{final}",
             'ManualDisbursement', disburse.id)

    # Mettre à jour le transfert lié si succès
    if final == 'success' and disburse.transfer:
        disburse.transfer.status = 'success'
        disburse.transfer.save(update_fields=['status'])

    return JsonResponse({
        'status':         final,
        'raw_status':     raw_status,
        'transaction_id': disburse.transaction_id,
        'description':    check.get('description', ''),
        'updated_at':     disburse.updated_at.strftime('%d/%m/%Y %H:%M'),
    })


# =====================================
# JOURNAL D'AUDIT
# =====================================

@login_required
def admin_audit_log(request):
    from dashboard_admin.models import AuditLog
    logs = AuditLog.objects.select_related('admin').all()
    action_filter = request.GET.get('action', '')
    date_filter   = request.GET.get('date', '')
    if action_filter:
        logs = logs.filter(action=action_filter)
    if date_filter:
        try:
            logs = logs.filter(created_at__date=date_filter)
        except Exception:
            pass
    return render(request, 'custom_admin/admin/audit_log.html', {
        'logs':          logs[:200],
        'actions':       AuditLog.ACTIONS,
        'action_filter': action_filter,
        'date_filter':   date_filter,
    })


# =====================================
# STATS TEMPS RÉEL (JSON)
# =====================================

@login_required
def admin_dashboard_stats(request):
    from datetime import date as _date
    qs   = Transfer.objects.all()
    succ = qs.filter(status='success')
    total      = qs.count()
    succ_count = succ.count()
    revenue  = float(succ.aggregate(s=Sum('our_fee_amount'))['s'] or 0)
    volume   = float(succ.aggregate(s=Sum('amount_sent'))['s'] or 0)
    pd_fees  = float(
        (succ.aggregate(s=Sum('payin_fee_amount'))['s'] or 0) +
        (succ.aggregate(s=Sum('payout_fee_amount'))['s'] or 0)
    )
    return JsonResponse({
        'total_transfers':      total,
        'successful_transfers': succ_count,
        'pending_transfers':    qs.filter(status__in=['created', 'invoice_sent', 'debited', 'disbursing']).count(),
        'failed_transfers':     qs.filter(status='failed').count(),
        'transfers_today':      qs.filter(created_at__date=_date.today()).count(),
        'total_users':          UserProfile.objects.count(),
        'our_revenue':          revenue,
        'total_volume':         volume,
        'paydunia_fees':        pd_fees,
        'success_rate':         round(succ_count / total * 100, 1) if total else 0,
        'average_transfer':     volume / succ_count if succ_count else 0,
    })
