"""Loopback-only TCP-to-TLS bridge with CA and hostname verification."""
import json
from pathlib import Path
import selectors
import socket
import ssl
import sys
import threading


def relay(left, right):
    selector = selectors.DefaultSelector()
    selector.register(left, selectors.EVENT_READ, right)
    selector.register(right, selectors.EVENT_READ, left)
    try:
        while True:
            events = selector.select(timeout=300)
            if not events:
                continue
            for key, _ in events:
                data = key.fileobj.recv(65536)
                if not data:
                    return
                key.data.sendall(data)
    finally:
        selector.close()
        left.close()
        right.close()


def handle(client, upstream, tls_name, context):
    try:
        raw = socket.create_connection(tuple(upstream), timeout=15)
        secured = context.wrap_socket(raw, server_hostname=tls_name)
        client.settimeout(None)
        secured.settimeout(None)
        relay(client, secured)
    except Exception as error:
        print(f'TLS bridge connection failed: {error}', file=sys.stderr, flush=True)
        client.close()


def main(settings_path):
    settings = json.loads(Path(settings_path).read_text())
    address, port = settings['upstream'].rsplit(':', 1)
    bridge_address, bridge_port = settings['bridge_addr'].rsplit(':', 1)
    context = ssl.create_default_context()
    with socket.create_server((bridge_address, int(bridge_port)), reuse_port=False) as server:
        server.listen(128)
        while True:
            client, _ = server.accept()
            threading.Thread(target=handle, args=(client, (address, int(port)),
                                                  settings['upstream_tls_name'], context),
                             daemon=True).start()


if __name__ == '__main__':
    main(sys.argv[1])
