from transfers.models import Transfer
from django.utils import timezone
from datetime import timedelta


def recredits_count(request):
    """Injecte le nombre de transferts à re-créditer dans tous les templates."""
    if not request.user.is_authenticated:
        return {'pending_recredits_count': 0}
    try:
        credit_failed = Transfer.objects.filter(status='credit_failed').count()
        stuck_threshold = timezone.now() - timedelta(minutes=10)
        stuck_debited = Transfer.objects.filter(
            status='debited',
            updated_at__lt=stuck_threshold
        ).count()
        return {'pending_recredits_count': credit_failed + stuck_debited}
    except Exception:
        return {'pending_recredits_count': 0}
