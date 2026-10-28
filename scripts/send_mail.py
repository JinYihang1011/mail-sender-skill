#!/usr/bin/env python3
"""Send one authorized message through SMTP with shared SQLite limits."""
import argparse
from contextlib import closing
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import smtplib
import sqlite3
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--to')
    parser.add_argument('--subject', required=True)
    parser.add_argument('--body-file', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    cfgpath = Path(args.config).expanduser().resolve()
    cfg = json.loads(cfgpath.read_text(encoding='utf-8'))
    recipient = args.to or cfg.get('default_to', '')
    sender = cfg['sender']
    required = [cfg['smtp_host'], cfg['username'], sender, recipient]
    if any(not x or x.startswith('YOUR_') for x in required):
        raise ValueError('Fill in SMTP host, username, sender and recipient before use.')
    if cfg['transport'] not in ('ssl', 'starttls'):
        raise ValueError('transport must be ssl or starttls')
    body = Path(args.body_file).read_text(encoding='utf-8')
    if cfg.get('signature'):
        body += '\n\n--\n' + cfg['signature']
    limits = cfg['limits']
    if any(not isinstance(limits[k], int) or limits[k] < 0 for k in ('min_interval_seconds','max_per_hour','max_per_day','dedupe_hours','cooldown_minutes')):
        raise ValueError('Limits must be non-negative integers.')
    digest = hashlib.sha256(json.dumps([recipient, args.subject, body], ensure_ascii=False).encode('utf-8')).hexdigest()
    statepath = Path(cfg['state_path']).expanduser()
    if not statepath.is_absolute():
        statepath = cfgpath.parent / statepath
    statepath.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(statepath, timeout=30)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS sends (ts TEXT NOT NULL, digest TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.commit()
        db.execute('BEGIN IMMEDIATE')
        now = dt.datetime.now()
        stamp = now.isoformat(timespec='seconds')
        cooldown = db.execute("SELECT value FROM metadata WHERE key='cooldown_until'").fetchone()
        recent = db.execute('SELECT ts, digest FROM sends').fetchall()
        reason = None
        if cooldown and now < dt.datetime.fromisoformat(cooldown[0]):
            reason = 'cooldown'
        elif sum(t.startswith(stamp[:10]) for t, _ in recent) >= limits['max_per_day']:
            reason = 'daily_limit'
        elif sum(t.startswith(stamp[:13]) for t, _ in recent) >= limits['max_per_hour']:
            reason = 'hourly_limit'
        elif recent and (now - max(dt.datetime.fromisoformat(t) for t, _ in recent)).total_seconds() < limits['min_interval_seconds']:
            reason = 'minimum_interval'
        elif any(d == digest and 0 <= (now - dt.datetime.fromisoformat(t)).total_seconds() < limits['dedupe_hours'] * 3600 for t, d in recent):
            reason = 'duplicate'
        if reason:
            print(json.dumps({'status': 'blocked', 'reason': reason}))
            return 2
        if args.dry_run:
            print(json.dumps({'status': 'dry_run', 'message': 'Configuration and limits checked; no message sent.'}))
            return 0
        password = os.environ.get(cfg['password_env'])
        if not password:
            raise ValueError('SMTP password environment variable is unset.')
        msg = EmailMessage()
        msg['From'] = formataddr((cfg.get('display_name', ''), sender))
        msg['To'] = recipient
        msg['Subject'] = args.subject
        msg.set_content(body)
        try:
            context = ssl.create_default_context()
            if cfg['transport'] == 'ssl':
                smtp = smtplib.SMTP_SSL(cfg['smtp_host'], cfg['smtp_port'], context=context, timeout=30)
            else:
                smtp = smtplib.SMTP(cfg['smtp_host'], cfg['smtp_port'], timeout=30)
                smtp.starttls(context=context)
            with smtp:
                smtp.login(cfg['username'], password)
                smtp.send_message(msg)
        except smtplib.SMTPResponseException as exc:
            if exc.smtp_code in (421, 450, 451, 452, 550, 554):
                until = (now + dt.timedelta(minutes=limits['cooldown_minutes'])).isoformat(timespec='seconds')
                db.execute("INSERT OR REPLACE INTO metadata VALUES ('cooldown_until', ?)", (until,))
                db.commit()
            print(json.dumps({'status': 'error', 'message': 'SMTP rejected or failed; delivery may be uncertain.', 'smtp_code': exc.smtp_code}))
            return 1
        db.execute('INSERT INTO sends VALUES (?, ?)', (stamp, digest))
        db.commit()
        print(json.dumps({'status': 'sent', 'message': 'Accepted by SMTP server; delivery is not confirmed.'}))
        return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'status': 'error', 'message': type(error).__name__ + ': operation failed; check configuration or network.'}))
        sys.exit(1)
