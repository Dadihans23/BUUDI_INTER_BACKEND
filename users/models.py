from django.db import models

# Create your models here.

class UserProfile(models.Model):
    phone = models.CharField(max_length=15, unique=True)  # ex: 0708091011
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"


