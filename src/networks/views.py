from src.networks.models import Network
from src.networks.serializers import NetworkSerializer
from rest_framework.viewsets import ModelViewSet


class NetworksModelView(ModelViewSet):
    """Return all supported networks."""

    serializer_class = NetworkSerializer
    queryset = Network.objects.all()
    lookup_field = "name"
