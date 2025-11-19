# users/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import UserProfile
from .serializers import UserProfileSerializer

class MeView(APIView):
    def get(self, request):
        phone = request.headers.get('X-User-Phone')  # Laravel envoie le phone
        if not phone:
            return Response({"error": "X-User-Phone manquant"}, status=400)

        try:
            profile = UserProfile.objects.get(phone=phone)
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response({"error": "Utilisateur non trouvé"}, status=404)