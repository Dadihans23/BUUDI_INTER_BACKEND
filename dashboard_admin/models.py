from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from users.models import UserProfile

class SupportTicket(models.Model):
    CATEGORIES = [
        ('reclamation', 'Réclamation'),
        ('question', 'Question'),
        ('bug', 'Bug'),
        ('autre', 'Autre'),
    ]
    STATUS = [
        ('open', 'Ouvert'),
        ('in_progress', 'En cours'),
        ('resolved', 'Résolu'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='support_tickets')
    category = models.CharField(max_length=20, choices=CATEGORIES)
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.subject} — {self.user.phone}"


class SupportMessage(models.Model):
    SENDERS = [
        ('user', 'User'),
        ('support', 'Support'),
    ]

    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=SENDERS)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender} — {self.content[:50]}"


class ManualDisbursement(models.Model):
    """Déboursement direct lancé manuellement depuis le dashboard admin."""

    STATUS = [
        ('pending',  'En attente'),
        ('success',  'Réussi'),
        ('failed',   'Échoué'),
    ]

    # Qui a lancé le déboursement
    admin = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='manual_disbursements'
    )

    # Bénéficiaire
    phone    = models.CharField(max_length=20)
    operator = models.CharField(max_length=40)   # withdraw_mode Paydunya, ex: wave-ci
    amount   = models.PositiveIntegerField()       # en FCFA, entier (pas de décimale)

    # Contexte (optionnel : lié à un transfert bloqué)
    transfer = models.ForeignKey(
        'transfers.Transfer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='manual_disbursements'
    )

    # Résultat Paydunya
    disburse_token  = models.CharField(max_length=100, blank=True)
    disburse_ref_id = models.CharField(max_length=60, blank=True)   # ADMIN<id>
    transaction_id  = models.CharField(max_length=100, blank=True)
    provider_ref    = models.CharField(max_length=100, blank=True)
    paydunya_status = models.CharField(max_length=20, blank=True)   # raw status Paydunya
    paydunya_desc   = models.TextField(blank=True)                   # description reçue

    status     = models.CharField(max_length=20, choices=STATUS, default='pending')
    notes      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"ADMIN#{self.id} → {self.phone} ({self.operator}) {self.amount} F [{self.status}]"


class AuditLog(models.Model):
    ACTIONS = [
        ('user_create',      'Créer utilisateur'),
        ('user_edit',        'Modifier utilisateur'),
        ('transfer_edit',    'Modifier transfert'),
        ('transfer_delete',  'Supprimer transfert'),
        ('transfer_retry',   'Relancer transfert'),
        ('credit_retry',     'Relancer crédit'),
        ('credit_retry_all', 'Relancer tous crédits'),
        ('reconcile',        'Réconciliation disbursing'),
        ('fee_edit',         'Modifier frais opérateur'),
        ('support_reply',    'Répondre ticket support'),
        ('support_resolve',  'Résoudre ticket support'),
        ('manual_disburse',  'Déboursement manuel'),
        ('disburse_check',   'Vérifier déboursement'),
    ]

    admin       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='audit_logs')
    action      = models.CharField(max_length=30, choices=ACTIONS)
    object_type = models.CharField(max_length=50, blank=True)
    object_id   = models.IntegerField(null=True, blank=True)
    summary     = models.TextField()
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        admin_str = self.admin.username if self.admin else 'system'
        return f"[{self.get_action_display()}] {admin_str} — {self.summary[:60]}"
