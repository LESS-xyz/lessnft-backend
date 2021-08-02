import random

from django.db import models
from django.contrib.auth.models import AbstractUser
from dds.utilities import get_timestamp_path
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save

from dds.settings import DEFAULT_AVATARS


class MasterUser(models.Model):
    address = models.CharField(max_length=42, default=None, null=True, blank=True, unique=True)
    commission = models.IntegerField()

    def save(self, *args, **kwargs):
        if not self.pk and MasterUser.objects.exists():
            raise ValidationError('There is can be only one MasterUser instance')
        return super(MasterUser, self).save(*args, **kwargs)


class AdvUser(AbstractUser):
    avatar = models.ImageField(blank=True, upload_to=get_timestamp_path)
    cover = models.ImageField(blank=True, upload_to=get_timestamp_path)
    display_name = models.CharField(max_length=50, default=None, null=True, blank=True)
    custom_url = models.CharField(max_length=80, default=None, null=True, blank=True, unique=True)
    bio = models.TextField(default=None, null=True, blank=True)
    twitter = models.CharField(max_length=80, default=None, null=True, blank=True)
    instagram = models.CharField(max_length=80, default=None, null=True, blank=True)
    site = models.CharField(max_length = 200, default=None, null=True, blank=True)
    is_verificated = models.BooleanField(default=False)

    def get_name(self):
        return self.display_name if self.display_name else self.username

    def __str__(self):
        return self.get_name()

def user_registrated_dispatcher(sender, instance, created, **kwargs):
    if created:
        instance.avatar = random.choice(DEFAULT_AVATARS)
        instance.save()


post_save.connect(user_registrated_dispatcher, sender=AdvUser)

class VerificationForm(models.Model):
    user = models.OneToOneField('AdvUser', on_delete=models.CASCADE)
    link = models.URLField(null=True, blank=True)
    eth_address = models.CharField(max_length=50, default=None, null=True, blank=True)
    role = models.CharField(max_length=20, choices=[('CREATOR', 'creator'), ('COLLECTOR', 'collector')])
    bio = models.TextField(null=True, blank=True)
    media = models.TextField(blank=True, null=True)
    twitter = models.CharField(max_length=80, default=None, null=True, blank=True)
    instagram = models.CharField(max_length=80, default=None, null=True, blank=True)
    site = models.URLField(null=True, blank=True)
    email = models.EmailField(max_length=80, default=None, null=True, blank=True)

    def save_form(self, request):
        self.link = request.data.get('url')
        self.eth_address = request.data.get('address')
        self.role = request.data.get('role')
        self.bio = request.data.get('bio')
        self.twitter = request.data.get('twitter')
        self.instagram = request.data.get('instagram')
        self.site = request.data.get('website')
        self.email = request.data.get('email')
        self.media = request.data.get('media')
        self.save()

    def __str__(self):
        return self.user.get_name()
