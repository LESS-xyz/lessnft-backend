from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from dds.rates.serializers import UsdRateSerializer
from dds.rates.models import UsdRate
from dds.settings import DEFAULT_NETWORK


rates_response = openapi.Response(
    description='WETH, ETC, USDC, LESS rates',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'WETH': openapi.Schema(type=openapi.TYPE_STRING),
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
        network = request.query_params.get('network', DEFAULT_NETWORK)
        rates = UsdRate.objects.filter(network__name__icontains=network).order_by('address')
        response_data = UsdRateSerializer(rates, many=True).data
        return Response(response_data, status=status.HTTP_200_OK)
