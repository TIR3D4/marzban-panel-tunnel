"""Operator commands; diagnostic output never dumps tokens or private keys."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import urllib.parse

from .installer import STATE, SOURCE, UNITS, apply, bundle, install, preflight
from .system import ETC, ROOT, install_runtime, run


def settings():
    if not STATE.exists():
        raise ValueError('Not configured. Run the installer first.')
    return json.loads(STATE.read_text())


def doctor(c):
    failures = []
    names = ['marzban-panel-tunnel'] + (['marzban-panel-nginx'] if c['role'] == 'iran' else [])
    if c['role'] == 'foreign' and c.get('upstream_protocol') == 'https':
        names.append('marzban-panel-tls-bridge')
    for name in names:
        result = subprocess.run(['systemctl', 'is-active', '--quiet', name])
        print(f'{name}: {"active" if result.returncode == 0 else "FAILED"}')
        if result.returncode:
            failures.append(name)
    if c['role'] == 'iran':
        url = f'http://127.0.0.1:{c["local_port"]}/dashboard/'
    else:
        url = f'https://{c["domain"]}/dashboard/'
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=15) as reply:
            if (reply.status != 200 or '/dashboard' not in reply.url
                    or urllib.parse.urlsplit(reply.url).netloc != urllib.parse.urlsplit(url).netloc):
                raise ValueError('Unexpected HTTP response or redirect.')
            print(f'End-to-end dashboard request: HTTP {reply.status}')
    except Exception as error:
        failures.append('dashboard request')
        print(f'Dashboard request FAILED: {error}')
    if c['role'] == 'iran':
        print('Also test https://' + c['domain'] + '/dashboard/ in an Iran browser; local checks cannot prove Iran reachability.')
    if failures:
        raise ValueError('Checks failed: ' + ', '.join(failures) + '. See docs/TROUBLESHOOTING.fa.md.')


def uninstall():
    preflight()
    c = settings()
    print('Stops/removes only project units and the command. Config, binary, certificates and packages are retained.')
    if input('Type REMOVE to continue: ').strip() != 'REMOVE':
        return
    for name in ['marzban-panel-tunnel', 'marzban-panel-nginx', 'marzban-panel-tls-bridge']:
        unit = UNITS / (name + '.service')
        if unit.exists():
            run('systemctl', 'disable', '--now', name)
            unit.unlink()
    Path('/usr/local/bin/panel-tunnel').unlink(missing_ok=True)
    Path('/etc/letsencrypt/renewal-hooks/deploy/marzban-panel-tunnel').unlink(missing_ok=True)
    run('systemctl', 'daemon-reload')
    print('Removed services. Saved config supports reinstall with: installer --resume')
    if c['role'] == 'iran':
        print('HTTPS renewal for this dedicated domain requires its gateway. Delete the unused certificate via certbot when retiring the domain.')


def main():
    parser = argparse.ArgumentParser(description='Encrypted Iran gateway for a Marzban dashboard')
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('install')
    p.add_argument('--role', choices=['iran', 'foreign'])
    p.add_argument('--resume', action='store_true')
    for name in ('doctor', 'status', 'logs', 'pair', 'update', 'uninstall', 'renew-test'):
        commands.add_parser(name)
    args = parser.parse_args()
    try:
        if args.command == 'install':
            install(args.role, args.resume)
        elif args.command == 'update':
            preflight()
            settings()
            if SOURCE == ROOT / 'app':
                raise ValueError('Download the current install.sh and run it with --update; the installed copy cannot fetch new source.')
            install_runtime(SOURCE)
            print('Application updated; config and binary remain unchanged. Run doctor.')
        elif args.command == 'uninstall':
            uninstall()
        else:
            if os.geteuid() != 0:
                raise ValueError('Run with sudo/root.')
            c = settings()
            if args.command == 'doctor':
                doctor(c)
            elif args.command == 'pair':
                if c['role'] != 'iran':
                    raise ValueError('Pairing codes are available only on the Iran server.')
                print(bundle(c))
            elif args.command == 'status':
                names = ['marzban-panel-tunnel'] + (['marzban-panel-nginx'] if c['role'] == 'iran' else [])
                if c['role'] == 'foreign' and c.get('upstream_protocol') == 'https':
                    names.append('marzban-panel-tls-bridge')
                return subprocess.run(['systemctl', 'status', '--no-pager', *names]).returncode
            elif args.command == 'logs':
                run('journalctl', '-u', 'marzban-panel-tunnel', '-u', 'marzban-panel-nginx',
                    '-u', 'marzban-panel-tls-bridge', '-n', '100', '--no-pager')
            elif args.command == 'renew-test':
                if c['role'] != 'iran':
                    raise ValueError('Run on the Iran gateway.')
                run('certbot', 'renew', '--cert-name', c['domain'], '--dry-run')
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        print('If install failed after saving config, retry with --resume; existing keys are retained.', file=sys.stderr)
        return 1
    return 0
