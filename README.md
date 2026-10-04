# Marzban Panel Tunnel

ورودی HTTPS برای پنل مرزبان از طریق سرور ایران، با **Rathole + Noise + Nginx**.

مرورگر شما به دامنه سرور ایران وصل می‌شود؛ سرور خارج اتصال خروجی رمزگذاری‌شده‌ای به ایران می‌سازد و درخواست‌های پنل را به Marzban محلی می‌رساند. حساب‌های مدیریت و ورود همان حساب‌های پنل اصلی هستند.

## شروع سریع

**پیش‌نیازها:** یک سرور ایران و یک سرور خارج با Debian 12+ یا Ubuntu 22.04+، معماری `x86_64`، دسترسی root/sudo و اینترنت برای دانلود بسته‌ها. Python 3 و curl باید موجود باشند. سرور ایران باید پورت‌های 80 و 443 آزاد داشته باشد. در نسخه 1.0، مرزبان باید روی سرور خارج یک endpoint محلی **HTTP** مثل `127.0.0.1:8000` داشته باشد. نصب‌کننده وجود داشبورد روی آن را بررسی می‌کند.

اگر curl یا Python نصب نیست:

```bash
sudo apt-get update && sudo apt-get install -y curl python3 ca-certificates
```

### ۱. DNS و فایروال

یک رکورد `A` بسازید:

| تنظیم | مقدار نمونه |
|---|---|
| نام | `panel-ir.hamrahgate.ir` |
| IP مقصد | IP عمومی سرور ایران |
| Cloudflare Proxy | خاموش: **DNS only** |

رکورد AAAA نگذارید، مگر اینکه خودتان مسیر IPv6 را تنظیم کرده باشید. این نسخه سرویس عمومی را روی IPv4 باز می‌کند.

روی ایران ورودی TCP پورت‌های **80، 443 و 2333** را در فایروال سیستم و فایروال ارائه‌دهنده باز کنید. پورت 2333 قابل انتخاب است؛ ترجیحاً فقط IP سرور خارج اجازه اتصال به آن داشته باشد. روی خارج اتصال خروجی به IP ایران روی همین پورت لازم است. پورت داخلی `18000` را عمومی باز نکنید. نصب‌کننده فایروال را خودکار تغییر نمی‌دهد.

### ۲. اجرا روی سرور ایران

```bash
curl -fsSL --retry 2 https://raw.githubusercontent.com/TIR3D4/marzban-panel-tunnel/main/install.sh -o /root/marzban-panel-tunnel-install.sh && bash /root/marzban-panel-tunnel-install.sh iran
```

دستور را در SSH با کاربر root اجرا کنید. با کاربر عادی، فایل را در پوشه خود دانلود و اسکریپت را با `sudo bash` اجرا کنید.

نصب‌کننده IP/hostname ایران، دامنه پنل، ایمیل گواهی و پورت تونل را می‌پرسد. دامنه پیش‌فرض `panel-ir.hamrahgate.ir` است. برای دریافت گواهی، DNS باید از قبل درست باشد و Let’s Encrypt بتواند به TCP/80 برسد. دریافت گواهی مستلزم پذیرش شرایط Let’s Encrypt است؛ نصب‌کننده آن را در حالت خودکار انجام می‌دهد.

در پایان **Pairing code** نمایش داده می‌شود. این کد محرمانه است؛ فقط در سرور خارج وارد کنید. کلید خصوصی ایران داخل این کد قرار نمی‌گیرد.

### ۳. اجرا روی سرور خارج، محل پنل Marzban

```bash
curl -fsSL --retry 2 https://raw.githubusercontent.com/TIR3D4/marzban-panel-tunnel/main/install.sh -o /root/marzban-panel-tunnel-install.sh && bash /root/marzban-panel-tunnel-install.sh foreign
```

کد مرحله قبل و آدرس محلی HTTP مرزبان را وارد کنید. پیش‌فرض `127.0.0.1:8000` است. کد هنگام تایپ/چسباندن نمایش داده نمی‌شود. نصب‌کننده قبل از راه‌اندازی دسترسی به endpoint محلی و پورت تونل ایران را بررسی می‌کند.

**اگر پورت مرزبان HTTPS است، این نسخه آن را به عنوان HTTP قبول نمی‌کند.** قبل از نصب، طبق [راهنمای نصب](docs/INSTALL.fa.md) endpoint مناسب را مشخص کنید؛ خاموش‌کردن TLS پنل اصلی یا تغییر Docker توسط این پروژه انجام نمی‌شود.

### ۴. تست نهایی

روی هر دو سرور:

```bash
sudo panel-tunnel doctor
```

روی خارج، درخواست HTTPS از دامنه ایران انجام می‌شود؛ روی ایران درخواست از سوکت داخلی تونل به خارج می‌رود. سپس از مرورگر **داخل ایران** باز کنید:

```text
https://panel-ir.hamrahgate.ir/dashboard/
```

شروع موفق سرویس به‌تنهایی به معنی موفقیت کل مسیر نیست. حتی نتیجه موفق `doctor` جای تست از اینترنت ایران را نمی‌گیرد. این پروژه کیفیت یا در دسترس بودن مسیر ایران↔خارج را تضمین نمی‌کند؛ خود سرور خارج باید بتواند به سرور ایران متصل شود.

## دستورات مدیریت

| دستور | کاربرد |
|---|---|
| `sudo panel-tunnel status` | وضعیت سرویس‌ها |
| `sudo panel-tunnel doctor` | بررسی سرویس‌ها و پاسخ HTTP مسیر تونل |
| `sudo panel-tunnel logs` | 100 خط آخر لاگ سرویس‌ها |
| `sudo panel-tunnel pair` | نمایش مجدد کد اتصال، فقط در ایران |
| `sudo panel-tunnel renew-test` | تست تمدید گواهی، فقط در ایران |
| `sudo panel-tunnel uninstall` | حذف سرویس‌های پروژه با تأیید `REMOVE` |

ادامه نصب نیمه‌تمام، بدون تولید مجدد کلید:

```bash
bash /root/marzban-panel-tunnel-install.sh --resume
```

به‌روزرسانی کد برنامه مدیریت، بدون تغییر کلیدها یا تنظیمات:

```bash
curl -fsSL --retry 2 https://raw.githubusercontent.com/TIR3D4/marzban-panel-tunnel/main/install.sh -o /root/marzban-panel-tunnel-install.sh && bash /root/marzban-panel-tunnel-install.sh --update
```

`--update` فقط کد مدیریت را به‌روزرسانی می‌کند؛ باینری Rathole، قالب سرویس‌ها و تنظیمات فعال را تغییر نمی‌دهد. برای اعمال مجدد قالب‌های نسخه جدید پس از بررسی تغییرات، `--resume` را اجرا کنید. این کار سرویس‌های پروژه را restart می‌کند.

## دامنه و محدوده پروژه

دامنه اصلی مثل `op1.hamrahgate.ir` به همان سرور قبلی اشاره می‌کند. مسیر جدید پنل جداگانه است. فقط مسیرهای `/dashboard/` و `/api` در دامنه جدید پروکسی می‌شوند؛ مسیر subscription و سایر مسیرها 404 می‌گیرند. `/api` همه امکانات مدیریت مرزبان را در دسترس قرار می‌دهد و احراز هویت آن با خود Marzban است.

هیچ تغییری در دیتابیس، کاربران، Nodeها، Xray، لینک subscription یا فایل‌های Marzban داده نمی‌شود. روی ایران بسته‌های Nginx و Certbot نصب می‌شوند؛ Nginx پروژه config و systemd unit مستقل دارد. اگر نصب‌کننده Nginx را تازه نصب کند، سرویس پیش‌فرض بسته را متوقف و غیرفعال می‌کند تا پورت‌های پروژه آزاد بمانند. برای یک VPS اختصاصی ایران طراحی شده است؛ با وب‌سرور فعال روی 80/443 نصب نمی‌شود.

## پوشه‌ها و آموزش

| مسیر | مسئولیت |
|---|---|
| `install.sh` | دانلود نسخه پروژه و شروع نصب |
| `manage.py` | ورودی CLI |
| `panel_tunnel/config.py` | اعتبارسنجی ورودی، تولید TOML و config Nginx/systemd |
| `panel_tunnel/system.py` | دانلود باینری با SHA-256 ثابت، نوشتن اتمیک فایل، عملیات سیستم |
| `panel_tunnel/installer.py` | مراحل نصب، جفت‌کردن دو سرور، گواهی و سرویس‌ها |
| `panel_tunnel/cli.py` | وضعیت، بررسی اتصال، لاگ، آپدیت و حذف |
| `tests/test_config.py` | تست قرارداد config و رد ورودی ناسالم |
| `tests/integration_tunnel.py` | تست واقعی انتقال HTTP و رد کلید نامعتبر با باینری Rathole |
| `.github/workflows/check.yml` | بررسی خودکار Python، تست‌ها و syntax اسکریپت |
| [docs/INSTALL.fa.md](docs/INSTALL.fa.md) | نصب و مثال فایروال |
| [docs/ARCHITECTURE.fa.md](docs/ARCHITECTURE.fa.md) | معماری، فایل‌های سیستم و مقادیر |
| [docs/TROUBLESHOOTING.fa.md](docs/TROUBLESHOOTING.fa.md) | عیب‌یابی و بازیابی |

## توسعه و تست

برنامه وابستگی pip ندارد و از کتابخانه استاندارد Python استفاده می‌کند. تست‌ها به Python 3.11+ نیاز دارند؛ برنامه نصب روی Python 3.10+ اجرا می‌شود.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q panel_tunnel manage.py
bash -n install.sh
```

تست واقعی با فایل باینری رسمی Rathole 0.5.0:

```bash
python3 tests/integration_tunnel.py /absolute/path/to/rathole
```

باینری Linux x64 نسخه `0.5.0` ثابت است و آرشیو دانلودشده با SHA-256 ثابت کنترل می‌شود. پشتیبانی ARM، چند پنل، WebSocket transport و endpoint محلی HTTPS در نسخه 1.0 پیاده‌سازی نشده‌اند.

منابع اصلی: [Rathole](https://github.com/rathole-org/rathole)، [Noise transport](https://github.com/rathole-org/rathole/blob/main/docs/transport.md)، [Certbot](https://eff-certbot.readthedocs.io/en/stable/using.html).
