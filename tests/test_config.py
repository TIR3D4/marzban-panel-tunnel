"""Configuration contract tests, including rejection of injected user inputs."""
import base64
import json
import http.server
import threading
import unittest
import tomllib

from panel_tunnel import config
from panel_tunnel.installer import bundle, unbundle, upstream_check

KEY = base64.b64encode(b'k' * 32).decode()
TOKEN = 'a' * 64


class ConfigurationTests(unittest.TestCase):
    def iran(self):
        return dict(role='iran', iran_host='192.0.2.1', domain='panel.example.com', port=2333,
                    local_port=18000, token=TOKEN, private_key=KEY, public_key=KEY)

    def test_iran_service_is_private_and_encrypted(self):
        c = tomllib.loads(config.rathole(self.iran()))['server']
        self.assertEqual(c['services']['panel']['bind_addr'], '127.0.0.1:18000')
        self.assertEqual(c['transport']['type'], 'noise')
        self.assertEqual(c['transport']['noise']['local_private_key'], KEY)

    def test_foreign_server_is_pinned_and_upstream_local(self):
        c = self.iran() | dict(role='foreign', upstream_protocol='http', upstream='127.0.0.1:8000')
        result = tomllib.loads(config.rathole(c))['client']
        self.assertEqual(result['remote_addr'], '192.0.2.1:2333')
        self.assertEqual(result['transport']['noise']['remote_public_key'], KEY)
        self.assertEqual(result['services']['panel']['local_addr'], '127.0.0.1:8000')

    def test_https_upstream_uses_verified_loopback_bridge(self):
        c = self.iran() | dict(role='foreign', upstream_protocol='https', upstream='127.0.0.1:443',
                               upstream_tls_name='panel.example.com', bridge_addr='127.0.0.1:18443')
        result = tomllib.loads(config.rathole(c))['client']
        self.assertEqual(result['services']['panel']['local_addr'], '127.0.0.1:18443')
        self.assertIn('Requires=marzban-panel-tls-bridge.service', config.tunnel_unit(c))
        self.assertIn('/etc/marzban-panel-tunnel/tls-bridge.json', config.tls_bridge_unit())

    def test_pairing_roundtrip_excludes_private_key(self):
        code = bundle(self.iran())
        decoded = json.loads(base64.urlsafe_b64decode(code))
        self.assertNotIn('private_key', decoded)
        self.assertEqual(unbundle(code)['token'], TOKEN)

    def test_pairing_rejects_untrusted_extra_fields(self):
        bad = self.iran()
        code = base64.urlsafe_b64encode(json.dumps(bad).encode()).decode()
        with self.assertRaises(ValueError):
            unbundle(code)

    def test_unsafe_input_is_rejected(self):
        for bad in ('example.com; reboot', 'a.com\ninclude /etc/passwd;', 'https://example.com', '../a.com'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                config.host(bad)
        for bad in ('192.0.2.1:8000', '127.0.0.1:65536', 'localhost:80', '127.0.0.1:80/path'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                config.upstream(bad)
        self.assertEqual(config.upstream_url('https://127.0.0.1:443')['upstream_protocol'], 'https')
        with self.assertRaises(ValueError):
            config.upstream_url('https://localhost:443')

    def test_no_subscription_route_and_forwarded_https(self):
        text = config.nginx(self.iran())
        self.assertIn('location / { return 404; }', text)
        self.assertIn('proxy_set_header X-Forwarded-Proto https;', text)
        self.assertIn('location ^~ /statics/', text)
        self.assertNotIn('location /sub', text)

    def test_local_upstream_and_redirect_detection(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            response = 200
            def do_GET(self):
                self.send_response(self.response)
                if self.response == 302:
                    self.send_header('Location', 'https://example.com/dashboard/')
                self.end_headers()
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            c = {'upstream_protocol': 'http', 'upstream': f'127.0.0.1:{server.server_port}'}
            upstream_check(c)
            Handler.response = 302
            with self.assertRaises(ValueError):
                upstream_check(c)
        finally:
            server.shutdown()
            server.server_close()

    def test_ports_keys_tokens(self):
        for bad in (0, 443, 65536):
            with self.assertRaises(ValueError):
                config.port(bad)
        with self.assertRaises(ValueError):
            config.key('abcd')
        with self.assertRaises(ValueError):
            config.token('short')


if __name__ == '__main__':
    unittest.main()
