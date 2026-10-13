<div dir="rtl">

# رها گیفت 🎁

وب‌سایت فارسی و راست‌به‌چپ «رها گیفت» با Django 6.1. شامل صفحه‌ی اصلی، مجموعه‌ی اشعار با فایل صوتی، و چت زنده (خصوصی و گروهی) بر پایه‌ی WebSocket.

## امکانات

- **حساب کاربری:** ثبت‌نام (قابل فعال/غیرفعال کردن از پنل ادمین) و ورود
- **ورود امن:** هر IP بعد از ۵ تلاش ناموفق، ۱۰ دقیقه مسدود می‌شود و تعداد تلاش‌های باقی‌مانده به کاربر نشان داده می‌شود
- **مجموعه‌ی اشعار:** همراه با فایل صوتی
- **چت زنده:** گفتگوی خصوصی و گروهی، ارسال فایل و پیام صوتی، پاسخ به پیام، بی‌صدا کردن، وضعیت آنلاین
- **حالت تیره و روشن**
- **نصب یک‌مرحله‌ای روی سرور:** nginx و SSL رایگان، به‌علاوه‌ی منوی مدیریتی `gift`

## اجرا روی سیستم خودتان

پیش‌نیاز: **Python 3.12 یا بالاتر**

</div>

```bash
git clone https://github.com/<your-username>/Raha_gift.git
cd Raha_gift
python -m venv venv
```

<div dir="rtl">

فعال‌سازی محیط مجازی، روی ویندوز:

</div>

```bash
venv\Scripts\activate
```

<div dir="rtl">

روی لینوکس و مک:

</div>

```bash
source venv/bin/activate
```

<div dir="rtl">

بعد نصب پکیج‌ها و راه‌اندازی:

</div>

```bash
pip install -r requirments.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

<div dir="rtl">

سایت روی `http://127.0.0.1:8000` و پنل ادمین روی `/admin/` باز می‌شود. ساختن فایل `.env` اختیاری است؛ بدون آن هم پروژه در حالت توسعه اجرا می‌شود.

اجرای تست‌ها:

</div>

```bash
python manage.py test
```

<div dir="rtl">

## نصب روی سرور (Production)

سرور: **Ubuntu 24.04+** یا **Debian 13+** با دسترسی root.

۱. در پنل دامنه، یک رکورد **A** بسازید که به IP سرور اشاره کند.

۲. پروژه را روی سرور بگیرید و نصب‌کننده را اجرا کنید:

</div>

```bash
git clone https://github.com/<your-username>/Raha_gift.git
cd Raha_gift
sudo bash deploy/install.sh
```

<div dir="rtl">

نصب‌کننده دامنه و یک ایمیل (برای Let's Encrypt) را می‌پرسد و بقیه‌ی کارها را خودش انجام می‌دهد:

- نصب Python، nginx و certbot
- کپی پروژه در `/opt/raha_gift` و ساخت محیط مجازی
- ساخت `SECRET_KEY` تصادفی و خاموش کردن DEBUG (در فایل `/etc/raha_gift/raha_gift.env`)
- اجرای migrate و collectstatic
- ساخت سرویس systemd به نام `raha-gift` (با daphne)
- تنظیم nginx (همراه با WebSocket برای چت)
- گرفتن گواهی SSL رایگان و ریدایرکت به https
- نصب منوی `gift`

**به‌روزرسانی:** کد جدید را بگیرید (`git pull`) و همان دستور نصب را دوباره بزنید. دیتابیس و فایل‌های آپلودشده دست نمی‌خورند.

### منوی مدیریت `gift`

روی سرور فقط بزنید:

</div>

```bash
gift
```

```
=========== Raha Gift ===========
  1) Start site
  2) Stop site
  3) Restart site
  4) Status & disk usage
  5) Delete chat messages
  6) Delete chat media
  7) Show site logs
  0) Exit
```

<div dir="rtl">

- **پاک کردن پیام‌ها و مدیای چت** برای وقتی است که فضای سرور کم شده. می‌شود فقط موارد قدیمی‌تر از چند روز را پاک کرد، و قبل از حذف تأیید گرفته می‌شود.
- **پاک کردن مدیا** فقط عکس، فایل و ویس‌های چت را پاک می‌کند و متن پیام‌ها می‌ماند.
- **دستور مستقیم:** `gift start`، `gift stop`، `gift restart` و `gift status` بدون باز کردن منو کار می‌کنند.

همین کارها از طریق دستور جنگو هم در دسترس است:

</div>

```bash
python manage.py cleanup_chat --media --older-than 30
python manage.py cleanup_chat --messages --older-than 90
```

<div dir="rtl">

## تنظیمات

همه‌ی تنظیمات با متغیرهای محیطی (یا فایل `.env`) انجام می‌شود. فهرست کامل با توضیح در [`.env.example`](.env.example) است.

| متغیر | توضیح |
|---|---|
| `DJANGO_SECRET_KEY` | کلید مخفی جنگو؛ در production حتماً مقدار تصادفی بگذارید |
| `DJANGO_DEBUG` | `1` برای توسعه و `0` برای production |
| `DJANGO_ALLOWED_HOSTS` | دامنه‌های مجاز، جدا با ویرگول |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | آدرس‌های کامل مجاز، مثل `https://example.com` |
| `DJANGO_HTTPS` | `1` وقتی سایت روی https است |
| `LOGIN_TRUST_CLOUDFLARE_IP` | `1` فقط اگر سایت پشت پروکسی Cloudflare است |

## ساختار پروژه

</div>

```
account/               ثبت‌نام، ورود امن و تنظیمات سایت
chat/                  چت زنده (WebSocket، آپلود فایل، گروه‌ها)
Collectionـofـpoems/   مجموعه‌ی اشعار
home/                  صفحه‌ی اصلی
config/                تنظیمات، آدرس‌ها و ASGI
templates/  static/    قالب‌ها و فایل‌های استاتیک
deploy/                install.sh و منوی gift
```
