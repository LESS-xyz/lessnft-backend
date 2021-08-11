from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from dds.rates.serializers import UsdRateSerializer
from dds.rates.models import UsdRate


rates_response = openapi.Response(
    description='ETH, BTC, USDC rates',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'ETH': openapi.Schema(type=openapi.TYPE_STRING),
            'ETC': openapi.Schema(type=openapi.TYPE_STRING),
            'USDC': openapi.Schema(type=openapi.TYPE_STRING),
            'LESS': openapi.Schema(type=openapi.TYPE_STRING),
        },
    )
)

class RateRequest(APIView):
    @swagger_auto_schema(
        operation_description="rate request",
        responses={200: rates_response}
    )
    def get(self, request):
        rates = UsdRate.objects.all()
        response_data = UsdRateSerializer(rates, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)
