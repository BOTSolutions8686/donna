# Donna Architecture

## Message Flow

### Incoming WhatsApp Message
1. Poll handler fetches new messages from ERPNext
   WhatsApp Message doctype every 2 minutes
2. normalize_phone() cleans the sender number
3. Contact classification:
   - Admin number → skip (Talha uses Telegram)
   - Team number → handle_team_message() [tickets + queries]
   - Anyone else → handle_customer_message()
4. Dedup check via wa_message_name in customer_conversations
5. Response sent via erp.send_whatsapp() with 24h window management

### Customer Message Handler
1. detect_language() — Arabic or English
2. Check if human has taken over — if yes, notify human, stop
3. Rate limit check (10 msg/hr)
4. Length check (500 chars max)
5. Anti-exploitation scan (16 patterns EN+AR)
6. Pending action state machine:
   - awaiting_email → collect email → schedule_customer_meeting()
7. Intent detection:
   - Meeting/schedule → collect email → Google Calendar + Meet
   - Immediate escalation triggers → trigger_escalation()
   - General → Claude Haiku API with pricing context
8. Post-response guardrail (no internal data leaks)
9. Log to customer_conversations table

### Escalation Flow
1. trigger_escalation() called by customer handler
2. Notify Talha via Telegram
3. Set 15-minute timer
4. If no response: auto-create ERPNext ticket, notify customer
5. Web dashboard: "Take" button → human takeover + WA notify

### Team Message Handler (handle_team_message)
- "status TKT-XXX" → ERPNext lookup
- "my tickets" / "open tickets" → filtered list
- "close TKT-XXX" / "resolve TKT-XXX" → guide to resolve command
- "create ticket: <text>" → new ERPNext ticket
- Anything else → "I can only help with tickets here"

### Poll Handler Logic (job_whatsapp_inbound_poll)
1. Fetch WhatsApp Messages since last poll
2. For each message:
   - Dedup check (wa_message_name already processed?)
   - normalize_phone(sender) → whitelist lookup
   - If not in whitelist → handle_customer_message()
   - If admin → skip (uses Telegram)
   - If team:
     - Log to team_conversations
     - Detect resolution language → post comment, alert Talha
     - Detect ticket ref → post comment
     - No context → handle_team_message() for intelligent response

## Database Schema (cloud_agent.db)
- contacts — all known phone numbers with type/status/language
- customer_conversations — full customer message history
- team_conversations — team message history with dedup
- customer_escalations — escalation tracking + status
- sessions — web dashboard auth tokens (24h TTL)
- suggestions — Donna self-improvement log
- gl_snapshots — daily financial snapshots
- whatsapp_conversations — 24h window tracking per number
- wa_poll_state — last poll timestamp
- pending_context — ticket-to-team-member link (48h)
- team_pending_state — queued messages for team
- sla_rules — SLA hours by priority

## Web Dashboard (port 8080)
- React 18 SPA served by FastAPI (web_api.py)
- Auth: ERPNext credentials → Bearer token in sessions table
- Roles: admin (all tools), team (Operations + Communication only)
- Financial tools: admin only (invoices, payables, P&L, etc.)
- Customer sidebar: live list with unread badges + escalation status
- Active conversation: 8s poll, intervention send button
- Tools panel: trigger any endpoint, results shown inline
- Donna chat: ask Claude questions about the business

## Config (config.py — never in git)
Required fields:
- erpnext.url, erpnext.api_key, erpnext.api_secret
- telegram.bot_token, telegram.allowed_user_id
- anthropic.api_key, anthropic.model
- db_path
- admin_users: list of ERPNext usernames with admin role
- team_members: [{name, email, whatsapp, role, works_on, access}]
- communication.whatsapp_whitelist: [{number, name, access}]

## Key Files
```
/opt/cloud_agent/
├── cloud_agent.py      # Main agent (~5400 lines)
├── database.py         # SQLite helpers (~1500 lines)
├── web_api.py          # FastAPI routes
├── erpnext_client.py   # ERPNext REST client
├── google_client.py    # Google Calendar/Gmail
├── config.py           # Credentials (gitignored)
├── cloud_agent.db      # SQLite database (gitignored)
├── web/
│   └── Donna.html      # React SPA frontend
├── logs/               # Rotating log files (gitignored)
│   ├── app.log
│   ├── error.log
│   └── whatsapp.log
├── docs/
│   ├── ARCHITECTURE.md
│   └── KNOWN_ISSUES.md
├── SESSION_LOG.md
├── DONNA_PLAN.md
└── README.md
```
