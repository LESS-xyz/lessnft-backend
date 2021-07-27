from rest_framework import serializers

from dds.accounts.models import AdvUser

class PatchSerializer(serializers.ModelSerializer):
    '''
    Serialiser for AdvUser model patching
    '''
    class Meta:
        model = AdvUser
        fields = ('display_name', 'avatar', 'custom_url', 'bio', 'twitter', 'instagram', 'site')

    def update(self, instance, validated_data):
        print('started patch')
        for attr, value in validated_data.items():
            if attr !='bio':
                my_filter = {attr: value}
                if attr == 'display_name' and value == '':
                    pass
                elif AdvUser.objects.filter(**my_filter).exclude(id=instance.id):
                    return {attr: f'this {attr} is occupied'}
            setattr(instance, attr, value)
        instance.save()
        return instance
