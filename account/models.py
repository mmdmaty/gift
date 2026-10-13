from django.db import models
from django.contrib.auth.models import AbstractBaseUser,AbstractUser

class CumstomUserModel(AbstractUser):
    class Meta(AbstractUser.Meta):
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"


class SiteSettings(models.Model):
    allow_registration = models.BooleanField(
        default=True,
        verbose_name="اجازه ساخت اکانت",
        help_text="در دیتابیس به‌صورت ۱ (فعال) و ۰ (غیرفعال) ذخیره می‌شود.",
    )

    class Meta:
        verbose_name = "تنظیمات ساخت اکانت"
        verbose_name_plural = "تنظیمات ساخت اکانت"

    def __str__(self):
        return "تنظیمات ساخت اکانت"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj



