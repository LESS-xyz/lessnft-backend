import random

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save

from src.utilities import get_media_from_ipfs


class DefaultAvatar(models.Model):
    image = models.CharField(max_length=200, blank=True, null=True, default=None)


class MasterUser(models.Model):
    address = models.CharField(max_length=42, default=None, null=True, blank=True)
    network = models.ForeignKey("networks.Network", on_delete=models.CASCADE)
    commission = models.IntegerField()


class AdvUserManager(UserManager):
    def get_by_custom_url(self, custom_url):
        """
        Return user by id or custom_url.

        Convert param to int() if it contains only digitts, because string params are not allowed
        in searching by id field. Numeric custom_urls should be prohibited on frontend
        """
        user_id = None
        if isinstance(custom_url, int) or custom_url.isdigit():
            user_id = int(custom_url)
        return self.get(Q(id=user_id) | Q(custom_url=custom_url))


class AdvUser(AbstractUser):
    avatar_ipfs = models.CharField(max_length=200, null=True, default=None)
    cover_ipfs = models.CharField(max_length=200, null=True, default=None, blank=True)
    display_name = models.CharField(max_length=50, default=None, null=True, blank=True)
    custom_url = models.CharField(
        max_length=80, default=None, null=True, blank=True, unique=True
    )
    bio = models.TextField(default=None, null=True, blank=True)
    twitter = models.CharField(max_length=80, default=None, null=True, blank=True)
    instagram = models.CharField(max_length=80, default=None, null=True, blank=True)
    facebook = models.CharField(max_length=80, default=None, null=True, blank=True)
    site = models.CharField(max_length=200, default=None, null=True, blank=True)
    is_verificated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AdvUserManager()

    def get_name(self):
        return self.display_name if self.display_name else self.username

    def __str__(self):
        return self.get_name()

    @property
    def avatar(self):
        return get_media_from_ipfs(self.avatar_ipfs)

    @property
    def cover(self):
        return get_media_from_ipfs(self.cover_ipfs)

    @property
    def url(self):
        return self.custom_url if self.custom_url else self.id


def user_registrated_dispatcher(sender, instance, created, **kwargs):
    if created:
        default_avatars = DefaultAvatar.objects.all().values_list("image", flat=True)
        if default_avatars:
            instance.avatar_ipfs = random.choice(default_avatars)
            instance.save()


post_save.connect(user_registrated_dispatcher, sender=AdvUser)


class VerificationForm(models.Model):
    user = models.OneToOneField("AdvUser", on_delete=models.CASCADE)
    link = models.URLField(null=True, blank=True)
    eth_address = models.CharField(max_length=50, default=None, null=True, blank=True)
    role = models.CharField(
        max_length=20, choices=[("CREATOR", "creator"), ("COLLECTOR", "collector")]
    )
    bio = models.TextField(null=True, blank=True)
    media = models.TextField(blank=True, null=True)
    twitter = models.CharField(max_length=80, default=None, null=True, blank=True)
    instagram = models.CharField(max_length=80, default=None, null=True, blank=True)
    site = models.URLField(null=True, blank=True)
    email = models.EmailField(max_length=80, default=None, null=True, blank=True)

    def save_form(self, request):
        self.link = request.data.get("custom_url")
        self.eth_address = request.data.get("address")
        self.role = request.data.get("role")
        self.bio = request.data.get("bio")
        self.twitter = request.data.get("twitter")
        self.instagram = request.data.get("instagram")
        self.site = request.data.get("site")
        self.email = request.data.get("email")
        self.media = request.data.get("media")
        self.save()

    def __str__(self):
        return self.user.get_name()
