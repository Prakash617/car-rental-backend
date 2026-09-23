import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class PlatformUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_platform_admin", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class PlatformUser(AbstractBaseUser, PermissionsMixin):
    """
    Central identity store in the public schema.
    A user has one account across all rental companies.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True, max_length=255)
    first_name = models.CharField("first name", max_length=60)
    last_name = models.CharField("last name", max_length=60)
    phone_number = models.CharField("phone number", max_length=30, blank=True, null=True)

    is_staff = models.BooleanField(
        "staff status",
        default=False,
        help_text="Designates whether the user can log into the Django admin site.",
    )
    is_platform_admin = models.BooleanField(
        "platform admin",
        default=False,
        help_text="Designates whether the user is a super-administrator of the SaaS platform.",
    )
    is_active = models.BooleanField(
        "active",
        default=True,
        help_text="Designates whether this user account should be treated as active.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlatformUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "Platform User"
        verbose_name_plural = "Platform Users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"], name="idx_platform_user_email"),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
