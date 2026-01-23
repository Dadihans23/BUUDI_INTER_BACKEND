from django.contrib import admin

# Register your models here.
from .models import Transfer , OperatorFees

admin.site.register(Transfer)
admin.site.register(OperatorFees)