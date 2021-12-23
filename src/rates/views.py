from src.rates.models import UsdRate
from src.rates.serializers import CurrencySerializer
from src.settings import config
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class RateRequest(APIView):
    @swagger_auto_schema(
        operation_description="rate request",
        responses={200: CurrencySerializer},
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        rates = UsdRate.objects.all()
        if network and network.lower() != "undefined":
            rates = rates.filter(network__name__icontains=network)
        rates = rates.order_by("address")
        response_data = CurrencySerializer(rates, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)
