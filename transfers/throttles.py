from rest_framework.throttling import AnonRateThrottle


class InitiateThrottle(AnonRateThrottle):
    """Max 10 initiations de transfert par minute par IP."""
    scope = 'initiate'


class ConfirmThrottle(AnonRateThrottle):
    """Max 5 confirmations OTP par minute par IP — anti brute-force."""
    scope = 'confirm'


class CreditThrottle(AnonRateThrottle):
    """Max 5 appels credit par minute par IP."""
    scope = 'credit'


class SupportThrottle(AnonRateThrottle):
    """Max 20 tickets créés par heure par IP."""
    scope = 'support'
