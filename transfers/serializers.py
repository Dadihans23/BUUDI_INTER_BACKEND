from rest_framework import serializers
from .models import Transfer

class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = [
            'id',
            'from_wallet',
            'to_wallet',
            'from_phone',
            'to_phone',
            'amount_requested',
            'amount_sent',
            'paydunya_invoice_token',
            'total_debited',
            'status',
            'created_at',
            
        ]
        read_only_fields = fields  # Ici c'est bon car fields est une liste