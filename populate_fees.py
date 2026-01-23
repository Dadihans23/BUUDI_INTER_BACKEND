import os
import django

# IMPORTANT : remplace "money_transfer.settings" par le bon chemin de tes settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'money_transfer.settings')  # adapte ici

django.setup()  # ← Initialise Django

from decimal import Decimal
from transfers.models import OperatorFees

from decimal import Decimal
from transfers.models import OperatorFees  

OPERATOR_FEES_DATA = [
    # Côte d'Ivoire
    {'operator': 'orange', 'payin': Decimal('2.500'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},
    {'operator': 'wave', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},
    {'operator': 'mtn', 'payin': Decimal('2.500'), 'payout': Decimal('2.500'), 'our': Decimal('1.500')},
    {'operator': 'moov', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},

    # Sénégal
    {'operator': 'orange-sénégal', 'payin': Decimal('2.500'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},
    {'operator': 'wave-sénégal', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},
    {'operator': 'free-money-sénégal', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},
    {'operator': 'emoney-sénégal', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},

    # Bénin
    {'operator': 'mtn-bénin', 'payin': Decimal('2.500'), 'payout': Decimal('2.500'), 'our': Decimal('1.500')},
    {'operator': 'moov-bénin', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},

    # Togo
    {'operator': 'tmoney-togo', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},
    {'operator': 'moov-togo', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},

    # Burkina Faso
    {'operator': 'orange-faso', 'payin': Decimal('2.500'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},
    {'operator': 'moov-faso', 'payin': Decimal('2.000'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},

    # Mali
    {'operator': 'orange-mali', 'payin': Decimal('2.500'), 'payout': Decimal('2.000'), 'our': Decimal('1.500')},
]

def populate_operator_fees():
    created = 0
    updated = 0

    for data in OPERATOR_FEES_DATA:
        operator_name = data['operator']
        defaults = {
            'payin_fee_percent': data['payin'],
            'payout_fee_percent': data['payout'],
            'our_fee_percent': data['our'],
        }

        obj, is_created = OperatorFees.objects.update_or_create(
            operator=operator_name,
            defaults=defaults
        )

        if is_created:
            created += 1
            print(f"Créé : {obj.operator} → Payin {obj.payin_fee_percent}% | Payout {obj.payout_fee_percent}% | Buudi {obj.our_fee_percent}%")
        else:
            updated += 1
            print(f"Mis à jour : {obj.operator} → Payin {obj.payin_fee_percent}% | Payout {obj.payout_fee_percent}% | Buudi {obj.our_fee_percent}%")

    print(f"\nTerminé ! {created} nouveaux frais créés, {updated} existants mis à jour.")

if __name__ == "__main__":
    populate_operator_fees()