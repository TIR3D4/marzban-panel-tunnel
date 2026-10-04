"""Interactive provisioning for Debian 12+ and Ubuntu 22.04+ x86_64."""
import base64
import getpass
import json
import os
import platform
import pwd
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import time
import urllib.request
import urllib.error

from . import config
from .system import ROOT, ETC, binary, install_runtime, run, write

UNITS = Path('/etc/systemd/system')
STATE = ETC / 'settings.json'
SOURCE = Path(__file__).resolve().parents[1]


def ask(label, default='', validator=lambda x: x, secret=False):
    while True:
        read = getpass.getpass if secret else input
        value = read(f'{label}' + (f' [{default}]' if default else '') + ': ').strip() or default
        try:
            return validator(value)
        except (ValueError, TypeError) as error:
            print(f'Invalid input: {error}')


def preflight():
    if os.geteuid() != 0:
        raise ValueError('Run with sudo/root.')
    if platform.machine() != 'x86_64':
        raise ValueError('Version 1.0 supports x86_64 only.')
    info = dict(line.strip().split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    distro, version = info.get('ID', '').strip('"'), info.get('VERSION_ID', '').strip('"')
    if not ((distro == 'debian' and int(version.split('.')[0]) >= 12) or
            (distro == 'ubuntu' and float(version) >= 22.04)):
        raise ValueError('Use Debian 12+ or Ubuntu 22.04+.')
    if not Path('/run/systemd/system').exists():
        raise ValueError('A host with systemd is required (not a container).')


def free_port(number):
    # Test both address families so an IPv6 wildcard listener is not overlooked.
    for family, address in ((socket.AF_INET, ('0.0.0.0', number)),
                            (socket.AF_INET6, ('::', number))):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                if family == socket.AF_INET6:
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                sock.bind(address)
        except OSError as error:
            if family == socket.AF_INET6 and error.errno in (97, 99):
                continue
            raise ValueError(f'Port {number} is unavailable. Use a dedicated Iran VPS or free the port first.') from error


def bundle(c):
    public = {name: c[name] for name in ('iran_host', 'port', 'public_key', 'token', 'domain')}
    return base64.urlsafe_b64encode(json.dumps(public).encode()).decode()


def unbundle(value):
    try:
        c = json.loads(base64.b64decode(value, altchars=b'-_', validate=True))
        if set(c) != {'iran_host', 'port', 'public_key', 'token', 'domain'}:
            raise ValueError('Unexpected pairing fields.')
        return dict(iran_host=config.host(c['iran_host']), port=config.port(c['port']),
                    public_key=config.key(c['public_key']), token=config.token(c['token']),
                    domain=config.host(c['domain']))
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError('Invalid pairing code; copy it again from the Iran server.') from error


def upstream_check(address):
    # No redirect following: a configured redirect can hide an inaccessible upstream.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open('http://' + address + '/dashboard/', timeout=10) as reply:
            if reply.status != 200:
                raise ValueError('Dashboard did not return HTTP 200.')
    except (urllib.error.URLError, OSError) as error:
        raise ValueError(f'Cannot read the local HTTP dashboard at {address}. Check Marzban port and HTTP/TLS mode.') from error


def gather(role):
    c = {'role': role}
    if role == 'iran':
        c['iran_host'] = ask('Iran public IPv4 or tunnel hostname', validator=config.host)
        c['domain'] = ask('New panel domain (DNS A must point to Iran)', 'panel-ir.hamrahgate.ir', config.host)
        try:
            socket.inet_aton(c['domain'])
        except OSError:
            pass
        else:
            raise ValueError('Panel domain must be a DNS name for public HTTPS.')
        if (Path('/etc/letsencrypt/renewal') / (c['domain'] + '.conf')).exists():
            raise ValueError('This domain already has a Certbot lineage. Choose a new dedicated domain.')
        c['email'] = ask('Email for Let\'s Encrypt', validator=email)
        c['port'] = ask('Tunnel TCP port', '2333', config.port)
        c['local_port'] = ask('Internal loopback proxy port', '18000', config.port)
        if c['port'] == c['local_port']:
            raise ValueError('Tunnel port and loopback port must differ.')
        for number in (80, 443, c['port'], c['local_port']):
            free_port(number)
        c['token'] = secrets.token_hex(32)
        generated = run(str(binary()), '--genkey', capture=True)
        keys = re.findall(r'(?:Private|Public) Key:\s*([A-Za-z0-9+/=]+)', generated)
        if len(keys) != 2:
            raise ValueError('Unexpected Rathole key output.')
        c['private_key'], c['public_key'] = map(config.key, keys)
    else:
        c.update(ask('Pairing code from Iran (hidden)', validator=unbundle, secret=True))
        c['upstream'] = ask('Local Marzban HTTP endpoint', '127.0.0.1:8000', config.upstream)
        upstream_check(c['upstream'])
        with socket.create_connection((c['iran_host'], c['port']), timeout=10):
            pass
    return c


def email(value):
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ValueError('Enter a valid email address.')
    return value


def apply(c):
    binary()
    try:
        pwd.getpwnam('marzban-panel-tunnel')
    except KeyError:
        run('useradd', '--system', '--no-create-home', '--shell', '/usr/sbin/nologin', 'marzban-panel-tunnel')
    ETC.mkdir(mode=0o750, parents=True, exist_ok=True)
    group = pwd.getpwnam('marzban-panel-tunnel').pw_gid
    os.chmod(ETC, 0o750)
    os.chown(ETC, 0, group)
    write(ETC / 'rathole.toml', config.rathole(c), 0o640)
    os.chown(ETC / 'rathole.toml', 0, group)
    install_runtime(SOURCE)
    write(UNITS / 'marzban-panel-tunnel.service', config.tunnel_unit(), 0o644)
    if c['role'] == 'iran':
        had_nginx = shutil.which('nginx') is not None or Path('/usr/sbin/nginx').exists()
        run('apt-get', 'update')
        run('apt-get', 'install', '-y', 'nginx', 'certbot')
        # Stop only the default service installed by this invocation, never an existing one.
        if not had_nginx:
            run('systemctl', 'disable', '--now', 'nginx')
        cert = Path('/etc/letsencrypt/live') / c['domain'] / 'fullchain.pem'
        Path('/var/log/marzban-panel-tunnel').mkdir(parents=True, exist_ok=True)
        Path('/var/lib/marzban-panel-tunnel/acme').mkdir(parents=True, exist_ok=True)
        if not cert.exists():
            print('Obtaining HTTPS certificate: DNS and inbound TCP/80 must already work.')
            bootstrap = ETC / 'acme-bootstrap.conf'
            write(bootstrap, config.acme_nginx(c), 0o644)
            run('/usr/sbin/nginx', '-t', '-c', str(bootstrap))
            process = subprocess.Popen(['/usr/sbin/nginx', '-c', str(bootstrap), '-g', 'daemon off;'])
            try:
                time.sleep(0.5)
                if process.poll() is not None:
                    raise ValueError('Temporary ACME gateway could not start.')
                run('certbot', 'certonly', '--webroot', '-w', '/var/lib/marzban-panel-tunnel/acme',
                    '--non-interactive', '--agree-tos', '--email', c['email'],
                    '--cert-name', c['domain'], '-d', c['domain'])
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
        write(ETC / 'nginx.conf', config.nginx(c), 0o644)
        run('/usr/sbin/nginx', '-t', '-c', str(ETC / 'nginx.conf'))
        write(UNITS / 'marzban-panel-nginx.service', config.nginx_unit(), 0o644)
        write('/etc/letsencrypt/renewal-hooks/deploy/marzban-panel-tunnel',
              '#!/bin/sh\nif systemctl is-active --quiet marzban-panel-nginx; then systemctl reload marzban-panel-nginx; fi\n', 0o755)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'marzban-panel-tunnel')
    run('systemctl', 'restart', 'marzban-panel-tunnel')
    if c['role'] == 'iran':
        run('systemctl', 'enable', 'marzban-panel-nginx')
        run('systemctl', 'restart', 'marzban-panel-nginx')
    c['installed'] = True
    write(STATE, json.dumps(c, indent=2))
    print('Installed. This does not yet prove end-to-end connectivity; run: sudo panel-tunnel doctor')
    if c['role'] == 'iran':
        print('Pairing code (secret; paste only into your foreign server):\n' + bundle(c))
        print(f'Allow inbound TCP 80, 443, {c["port"]} in the Iran firewall/provider security group.')
    print(f'Panel: https://{c["domain"]}/dashboard/')


def install(role=None, resume=False):
    preflight()
    if resume:
        if not STATE.exists():
            raise ValueError('No pending configuration. Run install first.')
        c = json.loads(STATE.read_text())
    else:
        if STATE.exists():
            raise ValueError('Configuration exists. Use resume, doctor, update or uninstall; keys are preserved.')
        role = role or ask('Server role', validator=lambda v: v if v in ('iran', 'foreign') else invalid_role())
        c = gather(role)
        ETC.mkdir(mode=0o750, parents=True, exist_ok=True)
        c['installed'] = False
        write(STATE, json.dumps(c, indent=2))
    apply(c)


def invalid_role():
    raise ValueError('Choose iran or foreign.')
