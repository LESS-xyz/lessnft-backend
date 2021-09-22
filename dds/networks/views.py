from dds.networks.models import Network
from dds.networks.serializers import NetworkSerializer
from rest_framework.viewsets import ModelViewSet


class NetworksModelView(ModelViewSet):
    """Return all supported networks."""
    serializer_class = NetworkSerializer
    queryset = Network.objects.all()
    lookup_field = "name"
