# Donna — BOT Solutions Operations AI

Donna is an autonomous business operations agent for BOT Solutions,
an ERPNext implementation company in Saudi Arabia.

## What Donna Does
- Monitors ERPNext (helpdesk.botsolutions.tech) for tickets, 
  invoices, ZATCA compliance
- Handles customer WhatsApp conversations autonomously
- Escalates to human agents when needed
- Provides a web dashboard for team monitoring and intervention
- Sends proactive alerts via Telegram and WhatsApp

## Tech Stack
- Python 3 — main agent (cloud_agent.py)
- FastAPI — web server and API (runs inside cloud_agent.py)
- SQLite — local memory and state (cloud_agent.db)
- Telegram Bot API — admin interface
- Frappe WhatsApp — customer/team messaging
- ERPNext REST API — business data
- Google Calendar API — meeting scheduling
- React 18 — frontend dashboard (web/Donna.html)

## Server
- DigitalOcean Droplet: 165.232.114.90
- Ubuntu 24.04
- Systemd service: cloud_agent
- Web dashboard: http://165.232.114.90:8080

## File Structure
- cloud_agent.py — main agent, Telegram bot, FastAPI server
- database.py — all SQLite operations
- erpnext_client.py — ERPNext API client
- google_client.py — Google Calendar/Gmail client
- web_api.py — FastAPI route definitions
- web/Donna.html — frontend dashboard
- config.py — credentials (NOT in git)
- cloud_agent.db — SQLite database (NOT in git)
- logs/ — application logs (NOT in git)
- docs/ — architecture and planning docs
- SESSION_LOG.md — session history
- DONNA_PLAN.md — development roadmap

## Running Donna
```
systemctl start cloud_agent
systemctl stop cloud_agent
systemctl restart cloud_agent
systemctl status cloud_agent
```

## Logs
```
journalctl -u cloud_agent -f
tail -f logs/app.log
tail -f logs/error.log
tail -f logs/whatsapp.log
```

## Resume Any Claude Code Session
Read SESSION_LOG.md and DONNA_PLAN.md first, then check
`systemctl status cloud_agent` and recent logs before doing anything.
