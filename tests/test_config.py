"""Configuration contract tests, including rejection of injected user inputs."""
import base64
import json
import unittest
import tomllib

from panel_tunnel import config
from panel_tunnel.installer import bundle, unbundle

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
        c = self.iran() | dict(role='foreign', upstream='127.0.0.1:8000')
        result = tomllib.loads(config.rathole(c))['client']
        self.assertEqual(result['remote_addr'], '192.0.2.1:2333')
        self.assertEqual(result['transport']['noise']['remote_public_key'], KEY)
        self.assertEqual(result['services']['panel']['local_addr'], '127.0.0.1:8000')

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

    def test_no_subscription_route_and_forwarded_https(self):
        text = config.nginx(self.iran())
        self.assertIn('location / { return 404; }', text)
        self.assertIn('proxy_set_header X-Forwarded-Proto https;', text)
        self.assertNotIn('location /sub', text)

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
