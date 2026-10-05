"""Validate user input and render isolated Rathole/Nginx/systemd files."""
import base64
import ipaddress
import json
import re


def host(value):
    try:
        ipaddress.IPv4Address(value)
        return value
    except ValueError:
        if re.fullmatch(r'(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}', value):
            return value.lower()
    raise ValueError('Use an IPv4 address or a DNS hostname (without https:// or port).')


def port(value):
    number = int(value)
    if not 1024 <= number <= 65535:
        raise ValueError('Port must be 1024..65535.')
    return number


def key(value):
    if len(base64.b64decode(value, validate=True)) != 32:
        raise ValueError('Noise key must contain 32 bytes in base64.')
    return value


def token(value):
    if not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('Token must contain 64 lowercase hexadecimal characters.')
    return value


def upstream(value):
    if not re.fullmatch(r'127\.0\.0\.1:[0-9]{1,5}', value):
        raise ValueError('Upstream must be 127.0.0.1:PORT, e.g. 127.0.0.1:8000.')
    if not 1 <= int(value.rsplit(':', 1)[1]) <= 65535:
        raise ValueError('Invalid upstream port.')
    return value


def upstream_url(value):
    match = re.fullmatch(r'(http|https)://(127\.0\.0\.1:[0-9]{1,5})', value.lower())
    if not match:
        raise ValueError('Use http://127.0.0.1:PORT or https://127.0.0.1:PORT.')
    return {'upstream_protocol': match.group(1), 'upstream': upstream(match.group(2))}


def rathole(c):
    """The service socket on Iran is loopback-only; Noise authenticates the server."""
    q = json.dumps
    if c['role'] == 'iran':
        return f'''[server]
bind_addr = "0.0.0.0:{c['port']}"
[server.transport]
type = "noise"
[server.transport.noise]
local_private_key = {q(key(c['private_key']))}
[server.services.panel]
token = {q(token(c['token']))}
bind_addr = "127.0.0.1:{c['local_port']}"
'''
    local_addr = c['bridge_addr'] if c.get('upstream_protocol') == 'https' else c['upstream']
    return f'''[client]
remote_addr = {q(host(c['iran_host']) + ':' + str(port(c['port'])))}
[client.transport]
type = "noise"
[client.transport.noise]
remote_public_key = {q(key(c['public_key']))}
[client.services.panel]
token = {q(token(c['token']))}
local_addr = {q(upstream(local_addr))}
'''


def nginx(c):
    domain = host(c['domain'])
    # Only panel/API routes are forwarded. Subscription paths remain inaccessible here.
    return f'''pid /run/marzban-panel-nginx.pid;
user www-data;
worker_processes auto;
error_log /var/log/marzban-panel-tunnel/nginx-error.log;
events {{ worker_connections 1024; }}
http {{
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    server_tokens off;
    map $http_upgrade $connection_upgrade {{ default upgrade; '' close; }}
    access_log off;
    server {{
        listen 80;
        server_name {domain};
        location ^~ /.well-known/acme-challenge/ {{ root /var/lib/marzban-panel-tunnel/acme; }}
        location / {{ return 301 https://{domain}$request_uri; }}
    }}
    server {{
        listen 443 ssl;
        server_name {domain};
        ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        location = / {{ return 302 /dashboard/; }}
        location = /dashboard {{ return 302 /dashboard/; }}
        location ^~ /statics/ {{
            proxy_pass http://127.0.0.1:{c['local_port']};
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_read_timeout 300s;
        }}
        location ~ ^/(dashboard/|api(?:/|$)) {{
            proxy_pass http://127.0.0.1:{c['local_port']};
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_buffering off;
            proxy_read_timeout 300s;
            client_max_body_size 20m;
        }}
        location / {{ return 404; }}
    }}
}}
'''


def tunnel_unit(c=None):
    bridge_dependency = ''
    if c and c.get('upstream_protocol') == 'https':
        bridge_dependency = 'Requires=marzban-panel-tls-bridge.service\nAfter=marzban-panel-tls-bridge.service\n'
    return f'''[Unit]
Description=Marzban panel encrypted reverse tunnel
Wants=network-online.target
After=network-online.target
{bridge_dependency}StartLimitIntervalSec=0
StartLimitIntervalSec=0
[Service]
User=marzban-panel-tunnel
Group=marzban-panel-tunnel
ExecStart=/opt/marzban-panel-tunnel/bin/rathole /etc/marzban-panel-tunnel/rathole.toml
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
'''


def tls_bridge_unit():
    return '''[Unit]
Description=Verified TLS bridge for the local Marzban endpoint
Wants=network-online.target
After=network-online.target
[Service]
User=marzban-panel-tunnel
Group=marzban-panel-tunnel
ExecStart=/usr/bin/python3 /opt/marzban-panel-tunnel/app/panel_tunnel/tls_bridge.py /etc/marzban-panel-tunnel/tls-bridge.json
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
'''


def nginx_unit():
    return '''[Unit]
Description=HTTPS gateway for Marzban panel tunnel
After=network-online.target marzban-panel-tunnel.service
Wants=network-online.target
[Service]
Type=simple
ExecStartPre=/usr/sbin/nginx -t -c /etc/marzban-panel-tunnel/nginx.conf
ExecStart=/usr/sbin/nginx -c /etc/marzban-panel-tunnel/nginx.conf -g "daemon off;"
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
'''


def acme_nginx(c):
    """Temporary HTTP gateway for initial issuance; Certbot saves webroot renewal."""
    domain = host(c['domain'])
    return f'''pid /run/marzban-panel-acme.pid;
user www-data;
error_log /var/log/marzban-panel-tunnel/nginx-error.log;
events {{ worker_connections 64; }}
http {{
    access_log off;
    server {{
        listen 80;
        server_name {domain};
        location ^~ /.well-known/acme-challenge/ {{ root /var/lib/marzban-panel-tunnel/acme; }}
        location / {{ return 404; }}
    }}
}}
'''
