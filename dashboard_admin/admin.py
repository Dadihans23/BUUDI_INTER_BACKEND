from django.contrib import admin

# Register your models here.




# Register your models here.
from .models import *

admin.site.register(ManualDisbursement)
admin.site.register(SupportMessage)
admin.site.register(SupportTicket)

