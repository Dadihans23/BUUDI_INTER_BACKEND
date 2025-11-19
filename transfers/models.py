from django.db import models
from users.models import UserProfile
import decimal

class OperatorFees(models.Model):
    operator = models.CharField(max_length=20, unique=True)  # wave, moov, orange, mtn
    payin_fee_percent = models.DecimalField(max_digits=5, decimal_places=3, default=2.000)   # 2%
    payout_fee_percent = models.DecimalField(max_digits=5, decimal_places=3, default=2.000)  # 2%
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.operator.upper()} → Payin {self.payin_fee_percent}% | Payout {self.payout_fee_percent}%"


class Transfer(models.Model):
    STATUS = [
        ('created', 'Créé'),
        ('invoice_sent', 'Facture envoyée'),
        ('debited', 'Débité'),
        ('disbursing', 'En cours de crédit'),
        ('success', 'Réussi'),
        ('failed', 'Échoué'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    from_wallet = models.CharField(max_length=20)  # orange-money-ci
    to_wallet = models.CharField(max_length=20)   # moov-ci
    from_phone = models.CharField(max_length=15)
    to_phone = models.CharField(max_length=15)

    # Montants
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2 , default=0)  # 250.00 (ce que l'user veut envoyer)
    amount_sent = models.DecimalField(max_digits=12, decimal_places=2, default=0)      # = amount_requested
    our_fee_percent = models.DecimalField(max_digits=5, decimal_places=3, default=2.000)  # TA PART (2.0% recommandé)
    our_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payin_fee_percent = models.DecimalField(max_digits=5, decimal_places=3, default=0)
    payin_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payout_fee_percent = models.DecimalField(max_digits=5, decimal_places=3, default=0)
    payout_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    total_debited = models.DecimalField(max_digits=12, decimal_places=2 ,  default=0)  # Ce que l'user paie
    estimated_net_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Ta vraie marge

    paydunya_invoice_token = models.CharField(max_length=100, blank=True)
    paydunya_payment_ref = models.CharField(max_length=100, blank=True)
    disburse_token = models.CharField(max_length=100, blank=True)
    disburse_id = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.amount_requested} {self.from_wallet}→{self.to_wallet} (+{self.our_fee_amount} FCFA)"