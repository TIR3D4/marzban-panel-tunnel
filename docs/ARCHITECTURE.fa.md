# معماری و مقادیر

## مسیر درخواست

HTTPS مرورگر روی سرور ایران توسط Nginx باز می‌شود. Nginx مسیر پنل/API را به `127.0.0.1:18000` می‌دهد. Rathole ایران این درخواست را از اتصال Noise به Rathole خارج می‌فرستد. کلاینت خارج به `127.0.0.1:8000` روی host خودش متصل می‌شود و پاسخ در همان مسیر برمی‌گردد.

سرور ایران listener تونل را باز می‌کند؛ سرور خارج شروع‌کننده اتصال است. Noise ترافیک ایران↔خارج را رمزگذاری می‌کند و کلاینت کلید عمومی ایران را pin می‌کند. token مستقل به سرویس `panel` اجازه اتصال می‌دهد. مرورگر با گواهی معتبر HTTPS به ایران وصل می‌شود.

## فایل‌های نصب‌شده

| فایل/مسیر | هدف و دسترسی |
|---|---|
| `/opt/marzban-panel-tunnel/bin/rathole` | باینری ثابت 0.5.0 |
| `/opt/marzban-panel-tunnel/app/` | کد Python مدیریت |
| `/etc/marzban-panel-tunnel/settings.json` | state و کلیدهای نصب؛ root، حالت 600 |
| `/etc/marzban-panel-tunnel/rathole.toml` | config سرویس؛ root:marzban-panel-tunnel، حالت 640 |
| `/etc/marzban-panel-tunnel/acme-bootstrap.conf` | config موقت HTTP برای صدور اولیه گواهی |
| `/etc/marzban-panel-tunnel/nginx.conf` | config مستقل HTTPS در ایران |
| `/etc/systemd/system/marzban-panel-tunnel.service` | سرویس Rathole با کاربر اختصاصی بدون shell |
| `/etc/systemd/system/marzban-panel-nginx.service` | Nginx مستقل پروژه، فقط ایران |
| `/usr/local/bin/panel-tunnel` | فرمان مدیریت |
| `/var/log/marzban-panel-tunnel/nginx-error.log` | خطای reverse proxy؛ access log غیرفعال است |
| `/var/lib/marzban-panel-tunnel/acme` | webroot تمدید گواهی |
| `/etc/letsencrypt/live/DOMAIN/` | گواهی اختصاصی دامنه دوم |
| `/etc/letsencrypt/renewal-hooks/deploy/marzban-panel-tunnel` | reload بعد از تمدید |

## توضیح مقدارها

| مقدار | پیش‌فرض/معنی |
|---|---|
| `role` | `iran` یا `foreign`؛ محل اجرای installer |
| `iran_host` | IPv4 عمومی یا hostname بدون scheme/port؛ مقصد اتصال خارج |
| `domain` | دامنه ورودی دوم پنل، پیش‌فرض `panel-ir.hamrahgate.ir` |
| `port` | TCP تونل عمومی، پیش‌فرض 2333؛ هر دو طرف یکسان |
| `local_port` | سوکت خصوصی ایران، پیش‌فرض 18000 |
| `upstream` | endpoint HTTP روی host خارج؛ پیش‌فرض `127.0.0.1:8000` |
| `token` | 32 بایت تصادفی به شکل 64 کاراکتر hex؛ محرمانه |
| `private_key` | کلید خصوصی Noise؛ فقط ایران |
| `public_key` | کلید عمومی ایران برای pin در خارج |
| `email` | ایمیل گواهی Let’s Encrypt؛ فقط ایران |
| `installed` | نشان پایان مراحل نصب؛ جای تست اتصال را نمی‌گیرد |

مقدارهای secret را در GitHub، issue، screenshot یا لاگ عمومی نگذارید. Pairing code هم محرمانه است؛ base64 رمزگذاری نیست.

## تغییر و توسعه

تابع‌های config خروجی مستقل تولید می‌کنند و ورودی‌ها را کنترل می‌کنند. عملیات شبکه/سیستم در `system.py` قرار دارد. مراحل نصب در `installer.py` و فرمان‌های اپراتور در `cli.py` هستند. تغییرات قالب را همراه تست قرارداد و تست binary بررسی کنید.

تغییر پورت تونل باید در state هر دو طرف و firewall هماهنگ باشد. تغییر domain نیازمند DNS و صدور گواهی جدید است؛ صرف ادیت JSON کافی نیست. در نسخه 1.0، CLI تغییر دامنه/چرخش کلید خودکار ندارد. `--resume` از state ذخیره‌شده استفاده و فایل‌های تولیدشده را بازسازی می‌کند؛ ادیت دستی TOML با resume بازنویسی می‌شود.

باینری از upstream دانلود و با hash ثابت مقایسه می‌شود. این hash یک کنترل ثبات فایل دانلود است؛ جای امضای رسمی upstream را نمی‌گیرد. تغییر نسخه نیازمند بررسی release، hash، سازگاری transport و تست واقعی است. فایل‌های repo هیچ secret عملیاتی ندارند.
