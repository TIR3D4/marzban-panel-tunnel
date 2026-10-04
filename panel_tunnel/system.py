"""Host operations: bounded downloads, pinned binary, files and subprocesses."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile
import io

ROOT = Path('/opt/marzban-panel-tunnel')
ETC = Path('/etc/marzban-panel-tunnel')
RATHOLE_VERSION = '0.5.0'
RATHOLE_SHA256 = '3e7d0d0f365120cd3cd351d147d1a12ee960c8068b464d4dd533a3821873b80e'
RATHOLE_URL = f'https://github.com/rathole-org/rathole/releases/download/v{RATHOLE_VERSION}/rathole-x86_64-unknown-linux-gnu.zip'


def run(*args, capture=False, timeout=900):
    result = subprocess.run(args, check=True, text=True, capture_output=capture, timeout=timeout)
    return result.stdout.strip() if capture else ''


def write(path, text, mode=0o600):
    """Atomic replacement; secret-bearing files never become world-readable."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    os.fchmod(fd, mode)
    with os.fdopen(fd, 'w') as output:
        output.write(text)
    os.replace(tmp, path)


def binary():
    target = ROOT / 'bin/rathole'
    if target.exists() and run(str(target), '--version', capture=True).endswith(RATHOLE_VERSION):
        return target
    request = urllib.request.Request(RATHOLE_URL, headers={'User-Agent': 'marzban-panel-tunnel/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        archive = response.read(20 * 1024 * 1024 + 1)
    if hashlib.sha256(archive).hexdigest() != RATHOLE_SHA256:
        raise ValueError('Rathole archive checksum mismatch; installation stopped.')
    data = zipfile.ZipFile(io.BytesIO(archive)).read('rathole')
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix('.tmp')
    temp.write_bytes(data)
    temp.chmod(0o755)
    run(str(temp), '--version', capture=True)
    os.replace(temp, target)
    return target


def install_runtime(source):
    """Copy only application code; do not overwrite config, certificates or logs."""
    app = ROOT / 'app'
    app.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / 'panel_tunnel', app / 'panel_tunnel', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(source / 'manage.py', app / 'manage.py')
    write('/usr/local/bin/panel-tunnel', '#!/bin/sh\nexec python3 /opt/marzban-panel-tunnel/app/manage.py "$@"\n', 0o755)
