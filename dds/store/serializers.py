from rest_framework import serializers

from dds.store.models import Token

class TokenPatchSerializer(serializers.ModelSerializer):
    '''
    Serialiser for AdvUser model patching
    '''
    class Meta:
        model = Token
        fields = ('price', 'currency', 'selling', 'minimal_bid')

    def update(self, instance, validated_data):
        print('started patch')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
