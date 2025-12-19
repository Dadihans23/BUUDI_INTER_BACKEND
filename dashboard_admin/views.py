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
from io import StringIO, BytesIO

# Django
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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

# Apps du projet
from transfers.models import Transfer, OperatorFees
from users.models import UserProfile

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
    paginator = Paginator(users, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'custom_admin/admin/users.html', {'page_obj': page_obj})

@login_required
def admin_user_detail(request, user_id):
    user = get_object_or_404(UserProfile, id=user_id)
    transfers = user.transfer_set.all().order_by('-created_at')[:20]
    return render(request, 'custom_admin/admin/user_detail.html', {'user': user, 'transfers': transfers})

@login_required
def admin_user_edit(request, user_id):
    user = get_object_or_404(UserProfile, id=user_id)
    if request.method == 'POST':
        user.name = request.POST.get('name')
        user.phone = request.POST.get('phone')
        user.save()
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
            UserProfile.objects.create(phone=phone, name=name)
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
        # À adapter selon tes besoins (ex: changer statut manuellement)
        transfer.status = request.POST.get('status', transfer.status)
        transfer.save()
        messages.success(request, "Transfert mis à jour !")
        return redirect('custom_admin:transfer_detail', transfer_id=transfer.id)
    return render(request, 'custom_admin/admin/transfer_edit.html', {'transfer': transfer})

@login_required
def admin_transfer_delete(request, transfer_id):
    transfer = get_object_or_404(Transfer, id=transfer_id)
    if request.method == 'POST':
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
        messages.success(request, "Transfert remis en file d’attente pour réessai.")
    return redirect('custom_admin:transfer_detail', transfer_id=transfer.id)


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
        fee.payin_fee_percent = Decimal(request.POST.get('payin_fee_percent'))
        fee.payout_fee_percent = Decimal(request.POST.get('payout_fee_percent'))
        fee.save()
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