import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'send_mail.py'
spec = importlib.util.spec_from_file_location('sender', SCRIPT)
sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender)


class FakeSMTP:
    messages = []
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def login(self, *args): pass
    def send_message(self, msg): self.messages.append(msg)


class SenderTests(unittest.TestCase):
    def test_send_then_rate_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = {'smtp_host': 'smtp.example.invalid', 'smtp_port': 465, 'transport': 'ssl',
                   'username': 'user', 'sender': 'sender@example.invalid', 'display_name': 'Test',
                   'password_env': 'TEST_SMTP_PASSWORD', 'state_path': 'state.sqlite3', 'signature': 'Test signature',
                   'limits': {'min_interval_seconds': 600, 'max_per_hour': 6, 'max_per_day': 30,
                              'dedupe_hours': 24, 'cooldown_minutes': 30}}
            (root / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
            (root / 'body.txt').write_text('Hello', encoding='utf-8')
            args = ['send_mail.py', '--config', str(root / 'config.json'), '--to', 'recipient@example.invalid',
                    '--subject', 'Test', '--body-file', str(root / 'body.txt')]
            FakeSMTP.messages.clear()
            with patch.object(sender.sys, 'argv', args), patch.object(sender.smtplib, 'SMTP_SSL', FakeSMTP), patch.dict(os.environ, {'TEST_SMTP_PASSWORD': 'not-a-real-secret'}):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(sender.main(), 0)
                    self.assertEqual(sender.main(), 2)
            self.assertEqual(len(FakeSMTP.messages), 1)
            self.assertIn('Test signature', FakeSMTP.messages[0].get_content())
            self.assertIn('Test', FakeSMTP.messages[0]['From'])

    def test_dry_run_does_not_connect_or_need_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = json.loads((SCRIPT.parents[1] / 'config.example.json').read_text(encoding='utf-8'))
            cfg.update(smtp_host='smtp.example.invalid', username='user', sender='sender@example.invalid')
            (root / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
            (root / 'body.txt').write_text('Hello', encoding='utf-8')
            args = ['send_mail.py', '--config', str(root / 'config.json'), '--to', 'recipient@example.invalid',
                    '--subject', 'Test', '--body-file', str(root / 'body.txt'), '--dry-run']
            with patch.object(sender.sys, 'argv', args), patch.object(sender.smtplib, 'SMTP_SSL', side_effect=AssertionError('network called')):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(sender.main(), 0)


if __name__ == '__main__':
    unittest.main()
