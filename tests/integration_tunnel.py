"""Opt-in real binary test: noise tunnel, HTML payload, wrong-key rejection.
Usage: python3 tests/integration_tunnel.py /absolute/path/to/rathole
No root, systemd, firewall changes, or internet needed once the binary is present.
"""
import base64
import http.server
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from panel_tunnel.config import rathole


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'panel-tunnel-integration-ok')
    def log_message(self, *args):
        pass


def main(binary):
    private, public = re.findall(r'(?:Private|Public) Key:\s*(\S+)',
                                subprocess.check_output([binary, '--genkey'], text=True))
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    c = dict(role='iran', iran_host='127.0.0.1', port=free_port(), local_port=free_port(),
             private_key=private, public_key=public, token='a' * 64)
    processes = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with tempfile.TemporaryDirectory() as directory:
            server = Path(directory) / 'server.toml'
            client = Path(directory) / 'client.toml'
            server.write_text(rathole(c))
            client_c = c | dict(role='foreign', upstream=f'127.0.0.1:{httpd.server_port}')
            client.write_text(rathole(client_c))
            log = open(Path(directory) / 'process.log', 'w+')
            for path in (server, client):
                processes.append(subprocess.Popen([binary, str(path)], stdout=log, stderr=log))
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    with opener.open(f'http://127.0.0.1:{c["local_port"]}/dashboard/', timeout=1) as response:
                        assert response.read() == b'panel-tunnel-integration-ok'
                    break
                except (OSError, ValueError):
                    time.sleep(0.15)
            else:
                log.seek(0)
                raise AssertionError('Tunnel did not pass HTTP: ' + log.read())
            print('PASS: real Noise tunnel forwarded exact HTTP payload')
            processes[1].terminate()
            processes[1].wait(timeout=5)
            # Start a client that trusts the wrong server key. HTTP must not succeed.
            client_c['public_key'] = base64.b64encode(b'x' * 32).decode()
            client.write_text(rathole(client_c))
            processes.append(subprocess.Popen([binary, str(client)], stdout=log, stderr=log))
            time.sleep(1)
            try:
                with opener.open(f'http://127.0.0.1:{c["local_port"]}/dashboard/', timeout=2):
                    raise AssertionError('Wrong server key accepted')
            except OSError:
                pass
            print('PASS: wrong server key cannot forward HTTP')
            log.close()
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        httpd.shutdown()
        httpd.server_close()


if __name__ == '__main__':
    main(sys.argv[1])
