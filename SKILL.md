---
name: mail-sender
description: Send a user-authorized email using a configured SMTP account, or diagnose this skill's sender and rate limits. Use when asked to send an email or set up SMTP-based email reminders.
---

# SMTP mail sender

Use `scripts/send_mail.py` for explicitly authorized email sending. Ask for the intended recipient and content if missing; use existing user authorization when it already specifies the recipient and purpose. Never expose, request in chat, or commit credentials. Do not send test mail or create recurring jobs unless the user authorizes them.

Copy `config.example.json` to a private location and fill in the SMTP settings, sender and optional default recipient. Obtain credentials from the environment variable named by `password_env`; the user enters the secret in their own environment. Configuration and state must remain outside the repository. SMTP SSL and STARTTLS are supported.

Run `python scripts/send_mail.py --config <private-config.json> --to <recipient> --subject <subject> --body-file <utf8-file> --dry-run` to verify configuration and limits without sending. Remove `--dry-run` only when sending is authorized. The process emits JSON: `sent` means the SMTP server accepted the message; `blocked` means rate limiting; `error` means failure. Do not claim delivery without recipient confirmation. An SMTP failure can leave delivery uncertain; do not automatically resend ambiguous failures.

All processes sharing the configured SQLite state file share limits: minimum interval, per calendar hour and day, duplicate suppression and cooldown. Do not bypass limits. A scheduler must be configured separately; this skill does not install or guarantee one. See README.md for setup.
