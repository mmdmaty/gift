from django.db import models
from django.contrib.auth import get_user_model

USER = get_user_model()


class Poem(models.Model):
    name = models.CharField("عنوان شعر", max_length=150)
    about = models.ForeignKey(
        to=USER,
        on_delete=models.CASCADE,
        related_name="about",
        verbose_name="برای کاربر",
    )
    text = models.TextField("متن شعر")
    author = models.ForeignKey(
        to=USER,
        on_delete=models.PROTECT,
        related_name="author",
        verbose_name="نویسنده",
    )
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        verbose_name = "شعر"
        verbose_name_plural = "شعرها"
        ordering = ("-created_at",)

    def __str__(self):
        return self.name


class PoemSounds(models.Model):
    poem = models.ForeignKey(
        to=Poem,
        on_delete=models.CASCADE,
        related_name="sounds",
        verbose_name="شعر",
    )
    sound = models.FileField("فایل صوتی", upload_to="audio/")

    class Meta:
        verbose_name = "فایل صوتی"
        verbose_name_plural = "فایل‌های صوتی"

    def __str__(self):
        return f"صدا برای {self.poem.name}"
