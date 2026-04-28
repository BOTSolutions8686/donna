# Donna — Cloud Agent Development Plan

## Identity & Infrastructure
- Agent server: 165.232.114.90 (DigitalOcean, Ubuntu 24.04)
- Agent lives at: /opt/cloud_agent/
- Main file: cloud_agent.py
- Config file: /opt/cloud_agent/config.py
- Database: /opt/cloud_agent/cloud_agent.db (SQLite)
- Service: cloud_agent.service (systemd)
- Telegram ID allowed: 1594110510
- Personality: Donna Paulsen from Suits — direct, no fluff, dry wit
- ERPNext: Lavalon KSA Compliance app, Sales Order renamed to Proforma Invoice, standard Saudi chart of accounts

## Current Status
✅ get_overdue_invoices
✅ get_unconverted_proformas
✅ get_zatca_status
✅ get_gl_summary
✅ get_sales_summary
✅ get_payment_patterns
✅ detect_unusual_entries
✅ get_profit_and_loss
✅ get_balance_sheet
✅ get_proforma_details
✅ create_helpdesk_ticket
✅ update_helpdesk_ticket
✅ convert_proforma_to_invoice
✅ ZATCA check every 30 min
✅ Daily summary 9:00 AM Riyadh
✅ GL snapshot 00:05 AM Riyadh
✅ Conversation memory (last 24 messages in SQLite)
✅ ZATCA deduplication
✅ Write guard on all write operations
✅ Single-user restriction

## Milestone 1 — Quality & Completeness
- [x] 1.1 Smart daily summary — Claude-powered with day-over-day comparison ✅ 2026-04-16
- [x] 1.2 Submit Sales Invoice — submit draft, convert+submit chain, send PDF on Telegram 2705 2026-04-16
- [x] 1.3 Collections escalation tracker — SQLite tracker + weekly Monday 8am escalation job 2705 2026-04-16
- [x] 1.4 Vendor bills / payables — get_purchase_invoices + get_overdue_payables 2705 2026-04-16
- [x] 1.5 Long message handling — auto-split at 4096 chars ✅ 2026-04-16

## Milestone 2 — Self-Awareness & Suggestions Engine
- [x] 2.1 Suggestions table in SQLite 2705 2026-04-16
- [x] 2.2 Auto-logging triggers 2705 2026-04-16
- [x] 2.3 Suggestion commands 2705 2026-04-16
- [x] 2.4 Weekly suggestions digest Monday 8:15am 2705 2026-04-16

## Milestone 3 — Financial Intelligence Depth
- [x] 3.1 Historical GL trends from snapshots 2705 2026-04-16
- [x] 3.2 Cash flow forecast 30/60/90 day 2705 2026-04-16
- [x] 3.3 Customer credit risk scoring Green/Yellow/Red 2705 2026-04-16
- [x] 3.4 Monthly P&L digest 1st of month 9am 2705 2026-04-16

## Milestone 4 — Operations Expansion
- [x] 4.1 ZATCA retry — tries 4 known endpoints, self-logs suggestion if none work 2705 2026-04-16
- [x] 4.2 Stock monitoring — get_low_stock_items tool 2705 2026-04-16
- [x] 4.3 Instance health monitoring — daily 6am job + on-demand tool 2705 2026-04-16
- [x] 4.4 Multi-client foundation — erpnext_instances in config.py 2705 2026-04-16

## Production Switch
✅ Switched to production helpdesk.botsolutions.tech — 2026-04-16
- All tools verified: overdue invoices (9), proformas (6), ZATCA (7 logs), GL (17 entries), sales (12), payments (20), P&L, balance sheet, print formats, HD tickets
- UAT (metadaftr) kept as fallback under erpnext_instances
- SSL: 57 days remaining on prod cert
- Print formats on prod: Sales Invoice Print, ZATCA Phase 2 Print Format (default), Proforma Invoice (AQT) for Sales Orders

## Standing Rules — Follow Every Session
1. Always read cloud_agent.py before making any changes
2. Always read cloud_agent.db schema before touching the database
3. Test every change against UAT before considering it done
4. Never store credentials anywhere except config.py on the server
5. After any change restart service: systemctl restart cloud_agent && systemctl status cloud_agent
6. Keep CHANGELOG.md at /opt/cloud_agent/CHANGELOG.md — log every change with date
7. If a task fails or hits unexpected API structure, log it to suggestions table
8. Never modify production ERPNext — read-only until explicitly told otherwise
9. After completing any task — update DONNA_PLAN.md, mark task done with date ✅
10. After every session — append to SESSION_LOG.md: date, what was attempted, what was completed, what failed, what is next

## P2 — Communication Module

Phase A — Internal only (build first):
- [x] Email sending via ERPNext Communication doctype ✅ 2026-04-16 (needs ERPNext outgoing email account configured)
- [x] WhatsApp sending via frappe_whatsapp WhatsApp Message doctype ✅ 2026-04-16
- [x] Contacts limited to internal team only (Talha, Baraa) — whitelist in config.py ✅ 2026-04-16 (Talha, Al Baraa)
- [x] All sends require explicit confirmation ✅ 2026-04-16
- [x] Donna can notify team of ZATCA rejections, overdue summaries via email/WhatsApp ✅ 2026-04-16 rejections, overdue summaries, health alerts via email or WhatsApp as alternative to Telegram

Phase B — Client facing (same milestone, after Phase A is stable):
- [ ] Dry-run mode — Donna shows exactly what she would send before sending
- [ ] Template management — predefined templates only, no free-form to clients
- [ ] Send limits — max 1 message per customer per day
- [ ] Opt-out tracking in SQLite per customer
- [ ] Explicit enable/disable per customer
- [ ] Your approval required for first send to any new customer ever
- [ ] Separate confirmation flow for client-facing vs internal sends

## Donna Vision Statement

Donna is the operational nerve center for BOT Solutions. She is not just an ERPNext monitor — she is a Chief of Staff who knows everything happening in the business across every channel at all times.

### What Donna watches
- ERPNext: invoices, proformas, ZATCA, GL, stock, health
- Email: incoming and outgoing, summarised and actioned
- WhatsApp: incoming client and team messages, auto-ticket creation
- Helpdesk: all tickets, assignments, escalations, SLA breaches
- Calendar: meetings, deadlines, follow-ups
- Finance: cash position, collections, payables, trends

### What Donna does with it
- Maintains full context on every client at all times
- Briefs Talha before interactions so he never goes in blind
- Flags anything that needs attention before it becomes a problem
- Drafts responses, creates tickets, sends documents — always with approval
- Nothing falls through the cracks because Donna tracks every open item until closed

### Multi-user access (future)
- Whitelisted team members (starting with Al Baraa) can interact with Donna via WhatsApp Business API
- Donna responds with relevant ERPNext data — ticket status, client info, invoice details
- Access is read-only for team, write operations remain Talha-only
- Uses existing Frappe WhatsApp integration — no new infrastructure needed

### Multi-client (in progress)
- Each client ERPNext instance is onboarded separately
- Donna monitors all instances from one place
- Talha can switch context: "check ZATCA for client X"
- Foundation already built in Milestone 4.4

### Core principle
Talha manages people and makes decisions.
Donna manages information and executes operations.

## Milestone 5 — Chief of Staff Mode
Donna's long-term vision: handle everything behind client interactions so nothing falls through the cracks.

### Phase 1 — Communication Intake
- [ ] Connect to ERPNext email inbox via API — read incoming emails
- [x] Monitor incoming WhatsApp messages via Frappe WhatsApp app API -- WhatsApp Message DocType polling every 2min ✅ 2026-04-21
- [ ] Accept and transcribe voice notes via speech-to-text
- [ ] Accept documents and images forwarded by Talha — extract and understand content

### Phase 2 — Intelligence Layer
- [x] Daily morning email summary — categorised by urgency and client -- email_check job every 30min + Telegram alert ✅ 2026-04-21
- [ ] Client context engine — before any client interaction Donna briefs: open invoices, tickets, payment history, last communication tone
- [ ] Sentiment detection — flag when a client communication tone shifts negative
- [ ] Interaction briefing on demand — "brief me on Client X before my call"

### Phase 3 — Auto-Action
- [ ] Suggest email replies — draft response, Talha approves before sending
- [ ] Auto-create helpdesk tickets from incoming WhatsApp and email
- [ ] Auto-assign tickets based on content and team availability
- [ ] Send invoice PDFs on client request via email or WhatsApp
- [ ] Log all interactions to ERPNext CRM automatically

### Phase 4 — Proactive Operations
- [x] Daily morning briefing without being asked — morning team briefing at 8:30am Riyadh per member ✅ 2026-04-21
- [ ] Predictive cash crunch alerts — 30/60/90 day forward view
- [ ] Client churn signals — detect disengagement patterns early
- [x] Escalation handling end-to-end — SLA check 8:45am + 5pm Riyadh, agent-direct alerts, 90-day filter, 12h dedup ✅ 2026-04-21
- [ ] Nothing falls through the cracks — Donna tracks every open item until closed

### Multi-user WhatsApp access
- Whitelisted team member numbers (starting with Al Baraa) can message Donna via Frappe WhatsApp integration
- Donna responds with relevant ERPNext data — ticket status, client info, invoice details
- Read-only for team members, write operations remain Talha-only
- Uses existing Frappe WhatsApp infrastructure — no new setup needed
- Non-essential for now, implement after Phase 1 is stable

Note: Build after P2 Communication Module is stable. Phase 1 is the foundation — nothing else in this milestone works without it.

## Milestone 6 — Accounting Intelligence Upgrade

Donna must deeply understand ERPNext accounting structure — not just read numbers but understand what they mean, why they exist, and how to create correct entries.

### Phase 1 — Chart of Accounts Understanding
- [ ] On startup and weekly, read full Chart of Accounts from ERPNext API
- [ ] Store in SQLite: account name, account type, account number, parent account, is_group, root_type (Asset/Liability/Equity/Income/Expense), company
- [ ] Build account tree structure in memory so Donna understands hierarchy
- [ ] Donna must know which accounts are: receivables, payables, cash, bank, revenue, COGS, expenses, VAT, retained earnings
- [ ] Donna must understand Saudi-specific accounts: ZATCA VAT output, VAT input, zakat provision
- [ ] Refresh account list when new accounts are detected

### Phase 2 — GL and Journal Entry Understanding
- [ ] Donna reads GL entries and understands: which account was debited, which was credited, what voucher type created it, what it means in business terms
- [ ] Donna can explain any GL entry in plain language when asked
- [ ] Donna understands double-entry — can validate that any journal entry she is asked to create is balanced (debits = credits)
- [ ] Donna flags GL entries that look incorrect — wrong account type used, unusual debit/credit direction for that account type
- [ ] Donna understands ERPNext voucher types: Sales Invoice, Purchase Invoice, Payment Entry, Journal Entry, Stock Entry, Expense Claim

### Phase 3 — Journal Entry Creation
- [ ] Add create_journal_entry tool
- [ ] Donna validates before creating:
     - Debits equal credits
     - Accounts exist in Chart of Accounts
     - Account types make sense for the transaction
     - Cost center provided if required
     - Company is correct
- [ ] Requires explicit confirmation before posting
- [ ] Supports common scenarios:
     - Manual adjustments
     - Accruals and provisions
     - Bank charges
     - Opening entries
     - Inter-company transfers
     - VAT adjustments
- [ ] After creation Donna explains what the entry does in plain language
- [ ] Log all created journal entries to SQLite with timestamp, accounts used, amounts, reference, who instructed

### Phase 4 — Accounting Advisory
- [ ] When Talha describes a transaction in plain language Donna suggests the correct journal entry
- [ ] Donna identifies the right accounts from Chart of Accounts context
- [ ] Donna flags if a requested entry seems incorrect for the situation
- [ ] Donna can reconcile: given a bank statement line, suggest the matching GL entry
- [ ] Donna understands Saudi VAT implications — knows when VAT accounts should be involved in an entry
- [ ] Donna can explain why a trial balance is off and suggest correcting entries

### Standing accounting rules for Donna
- Debits = Credits always, no exceptions
- Never post to group accounts — only to leaf accounts
- Never post to system accounts (Debtors, Creditors) directly — use sub-ledger documents instead
- Always include a meaningful remark on every journal entry
- Flag any entry over 50,000 SAR for extra confirmation
- Never create entries in closed fiscal periods
- Understand that in ERPNext Sales Invoices auto-post to Debtors and revenue accounts — do not duplicate via manual journal entry

### Milestone 5 Progress (2026-04-21)
- team_conversations table — full per-member message history
- whatsapp_conversations table — 24h window tracking
- email_memory table — per-contact email history
- processed_emails table — deduplication
- client_profiles table — schema ready
- sla_rules table — seeded (Urgent/High/Medium/Low)
- team_members_db table — synced from config at startup
- wa_poll_state table — polling state persistence
- Incoming WhatsApp polling every 2 minutes (ERPNext WhatsApp Message DocType, type=Incoming)
- SLA breach monitoring every 30 minutes
- Email check every 30 minutes with Telegram alert
- Morning team briefing at 8:30 AM Riyadh
- ask_claude_team: last 10 messages included as context
- wa_send_safe: now logs to team_conversations and updates window tracking

### WhatsApp Infrastructure (2026-04-22)
- [x] FIX 1: Dedup bug resolved — log_team_conversation now stores wa_message_name, dedup confirmed working
- [x] FIX 2: Delivery status tracking — job_delivery_check every 10min, alerts Talha on failed deliveries
- [x] FIX 3: Template sending fixed — use_template=1 and template field now included in WhatsApp Message doc
- [x] FIX 4: Conversation threading — thread_id, get_team_conversation tool, chronological view
- [x] FIX 5: Template awareness — whatsapp_templates SQLite table, 20 templates seeded, wa_send_safe uses use_case to pick right template

### New database functions added (2026-04-22)
- update_delivery_status(sent_wa_message_name, status)
- get_untracked_outbound(hours)
- get_or_create_thread_id(number, ticket_id, hours)
- get_conversation_thread(number, ticket_id, limit)
- get_template_for_use_case(use_case)

### New tools added (2026-04-22)
- get_team_conversation: show conversation history with any team member, optionally filtered by ticket

## Milestone 7 — Customer WhatsApp Module (2026-04-22)

### Architecture
- All inbound WhatsApp messages now routed by contact type:
  - admin (whitelist access=admin) → handled by existing admin flow
  - team (whitelist access=team) → handle_team_message (ticket-only)
  - unknown number → handle_customer_message (customer flow)

### Database tables added
- [x] contacts — customer registry (name, company, language, flagged, etc.)
- [x] customer_conversations — all customer WhatsApp messages (inbound + outbound)
- [x] customer_escalations — escalation records with status lifecycle

### Steps completed
- [x] Step 1: Contact classification system (DB tables + helper functions)
- [x] Step 2: Language detection (detect_language, Arabic unicode check)
- [x] Step 3: Contact classification in poll handler (unknown → customer route)
- [x] Step 4: Team message handler (ticket-only intent detector, 5 operations)
- [x] Step 5: Customer message handler (language, rate limit, anti-exploit, ticket flow, Claude)
- [x] Step 6: Escalation system (trigger_escalation, job_escalation_check, take command)
- [x] Step 7: Anti-exploitation guardrails (injection patterns EN+AR, rate limit, length cap, topic guardrail)
- [x] Step 8: API endpoints (/api/customers, /api/customers/{phone}/conversation, /api/escalations, POST /api/escalations/{id}/take)
- [x] Step 9: Frontend updates (liveCustomers polling, escalation polling, live customer conversations, Intervene → API)
- [x] Step 10: Config fields (escalation_timeout_minutes=15, customer_rate_limit_per_hour=10, customer_max_message_length=500)

### Scheduler (full list)
zatca(30min) | daily_summary(9am) | gl_snapshot(midnight) | health_check(6am)
collections_escalation(mon 8am) | suggestions_digest(mon 8:15am) | team_accountability(mon 8:30am)
team_reminders(9:30am daily) | monthly_pl(1st 9am) | refresh_coa(sun 11pm)
whatsapp_poll(2min) | email_check(30min) | delivery_check(10min)
sla_check(8:45am+5pm) | old_tickets_digest(mon 9am) | morning_briefing(8:30am)
escalation_check(5min)

### Pending
- Live test: send WA from unknown number, verify it appears in sidebar
- Escalation auto-ticket test (1-min timeout for testing)
- Contact name enrichment from ERPNext Customer doctype
- Template-based re-open flow for customers (window closed)

---

## STANDING RULES (added 2026-04-23)

**RULE: GitHub is the source of truth.**
Every session must end with:
```
cd /opt/cloud_agent
git add .
git commit -m "Session: <what was built/fixed>"
git push origin main
```
Never commit: config.py, cloud_agent.db, logs/, *.bak files.

---

## Session: 2026-04-23 — Auth, Team Routing, Project Structure

### Completed this session
- [x] FIX 1: normalize_phone() + team messages routed to handle_team_message() (no more "which ticket?" for general messages)
- [x] FIX 2: sessions table in DB + /api/auth/login, /api/auth/me, /api/auth/logout-token endpoints (real ERPNext auth)
- [x] FIX 3: Frontend login wired to /api/auth/login, Bearer token in authFetch, token verified on app load
- [x] FIX 4: Role-aware UI — Financial + System tools hidden from team role
- [x] FIX 5: admin_users added to config.py
- [x] Rotating file logs: logs/app.log, logs/error.log, logs/whatsapp.log
- [x] wa_log.info() in handle_team_message and handle_customer_message entry points
- [x] README.md, docs/ARCHITECTURE.md, docs/KNOWN_ISSUES.md, config.example.json
- [x] .gitignore set up (excludes config.py, *.db, logs/, *.bak)
- [x] Git repo initialized, initial commit: 13 files, 10815 lines

### Pending - next session
- [ ] Add GitHub remote and push (need GitHub repo URL from Talha)
- [ ] Test login flow end-to-end with real ERPNext credentials
- [ ] Verify Abdul Malik messages now route correctly in production
- [ ] Monitor whatsapp.log for real traffic
- [ ] Clean up *.bak files after confirming stability

---

## Milestone 8 — RBAC, Dedicated Meta App, Web UI Overhaul (2026-04-28)

### 8.1 — Dedicated Donna Meta App ✅ 2026-04-28
- Created separate Meta Cloud API app for Donna (App ID: 4557236414522831, v25.0)
- Updated config.py: new access_token, app_id, api_version v25.0 (phone_id unchanged)
- Removed ERPNext fan-out from `/whatsapp-incoming` POST handler in web_api.py
- Donna is now fully independent from ERPNext's Meta app
- Webhook URL: https://donna.botsolutions.tech/whatsapp-incoming (verify_token: frappewapp)
- Caddy simplified: all traffic → localhost:8080 (removed special /whatsapp-incoming → 8765 routing)

### 8.2 — Identity Fix ✅ 2026-04-28
- Root cause: `/api/chat` hardcoded `sender_name="Talha"` for all web chat users
- Added `_display_name_for(username)` helper: checks donna_users DB → team_members config → email parse
- Login response now includes `display_name` field
- Frontend extracts `display_name` from login response, uses it for initials + sidebar display
- `/api/auth/me` also returns `display_name`

### 8.3 — RBAC: donna_users + User Management ✅ 2026-04-28
- Added `donna_users` table: id, username, display_name, role, is_active, created_at, last_login
- `upsert_donna_user()`: called on every login, updates last_login, only upgrades role (never silently downgrades)
- User management API (admin-only): GET/PATCH role, PATCH name, PATCH deactivate/activate
- `UserMgmtPanel` React component in Donna.html: grouped by role, inline name editing, role selector, enable/disable toggle
- "User Management" added to System tools nav

### 8.4 — EOD Schedule Fixed to KSA Times ✅ 2026-04-28
- Root cause: APScheduler uses `timezone="Asia/Riyadh"` so `hour=` values ARE KSA hours
- EOD request: 13:45 → **16:30 KSA** (`hour=16, minute=30`)
- EOD summary: 15:30 → **16:55 KSA** (`hour=16, minute=55`)
- Server timezone: confirmed `Asia/Riyadh` via `timedatectl`
- Docstrings and startup log updated to reflect correct times

### 8.5 — Role System Overhaul (3 roles) ✅ 2026-04-28
- Roles: **admin** (full), **manager** (reports + customers, no settings/P&L), **support** (tickets + WA + customers)
- Role `agent` renamed to `support` throughout all code and DB
- `role_permissions` table: 15 permission flags seeded per role with correct defaults:
  - admin: all 15 permissions
  - manager: all except manage_users, manage_roles, manage_settings, view_financials
  - support: view/chat customers, send_whatsapp, claim_conversation, escalate_tickets, view_team_chat, view_email, send_email_draft
  - viewer: view_customers, view_reports only
- `db.has_permission(username, permission)` — checks via role_permissions table
- `db.get_role_permissions(role)` / `db.get_all_role_permissions()` — full matrix access
- `db.set_role_permission(role, permission, granted)` — toggle individual flag

### 8.6 — Dynamic Role Permissions Web UI ✅ 2026-04-28
- `RolePermissionsPanel` React component: admin-only, shows all 15 permissions as rows
- 3-column toggle switches for manager/support/viewer (admin always full, not editable)
- GET /api/permissions — returns full matrix + labels
- PATCH /api/permissions — toggle one flag (admin role protected from changes)
- "Role Permissions" added to System tools nav
- Financial tools section: changed from adminOnly → managerOnly (admin + manager)
- P&L Overview API endpoint: now requires admin auth
- TOOLS filter: handles both adminOnly and managerOnly section flags

### 8.7 — User Pre-creation + Improved User Management ✅ 2026-04-28
- POST /api/users — pre-create user before first login (no ERPNext account needed yet)
- "Add User" form in UserMgmtPanel: username/email, display name, role selector
- Login: looks up DB role BEFORE creating session — manager/support/viewer stored correctly
- Session role = actual DB role (not generic 'team')
- Session TTL extended: 24h → 7 days
- Fetch permissions from /api/auth/permissions after login; stored in loggedIn state

### 8.8 — Conversation Claiming ✅ 2026-04-28
- `conversation_claims` table: phone_number (PK), claimed_by, claimed_by_name, claimed_at, active
- `db.claim_conversation(phone, username, display_name)` — returns False if already claimed by someone else
- `db.release_conversation(phone, username)` — clears claim, un-pauses Donna
- When claimed: `donna_paused=1` set on contacts row, Donna logs inbound messages but sends no AI response
- POST /api/customers/{phone}/claim — requires `claim_conversation` permission
- POST /api/customers/{phone}/release — claimer or admin only
- GET /api/conversations/claims — all active claims
- `ClaimButton` React component in conversation header: shows claim/release UI with attribution
- Claimed conversations shown as amber in sidebar (was green)
- CustomerCard shows claimer name badge in sidebar list

### 8.9 — Outbound WhatsApp Composer ✅ 2026-04-28
- POST /api/whatsapp/send — send to any phone number (requires send_whatsapp permission)
- GET /api/whatsapp/check-window/{phone} — checks if 24h free-text window is open
- `OutboundWAComposer` React modal: phone input with 24h window indicator, message textarea, char counter
- "+ New" button in customers sidebar opens composer
- `register_send_whatsapp(fn)` in web_api.py — wired to `_send_customer_reply` via post_init

### 8.10 — Contact Enrichment ✅ 2026-04-28
- contacts table: added status, email, need_category, enriched_name, enriched_at, donna_paused, ticket_count
- `db.update_contact_enrichment(phone, **kwargs)` — update name/email/company/need_category/status
- PATCH /api/customers/{phone}/enrich — REST endpoint for manual enrichment from web UI
- GET /api/customers now includes claimed_by/claimed_by_name per contact

### 8.11 — EOD Summary for Managers ✅ 2026-04-28
- `job_eod_summary` now looks up all donna_users with role='manager' and sends them the EOD digest
- Matches manager email against team_members config to find WhatsApp number
- Haider (manager role) gets same full team EOD summary as Talha at 4:55 PM KSA

### 8.12 — Business Hours Helper ✅ 2026-04-28
- `_is_business_hours()` — True if KSA time is Sun–Thu 10am–5pm (Fri/Sat off)
- `_business_hours_message(lang)` — OOH message in English or Arabic
- Ready for use in customer message handler (not yet enforced automatically)

### 8.13 — Bug Fixes (code review) ✅ 2026-04-28
- **`_dispatch_inbound_whatsapp`**: whitelist is `[{number, name, ...}]` not strings — `set()` was crashing with `TypeError: unhashable type: 'dict'`. Fixed with set comprehension extracting `w["number"]`
- **`_dispatch_inbound_whatsapp`**: called `_process_whatsapp_message(phone, text, msg_id, sender_name)` with wrong arg order — function takes `(sender, sender_name, message)`. Fixed
- **`_fastapi_wa_dispatch`**: called nonexistent `_handle_delivery_status(phone, status)`. Replaced with inline `db.update_delivery_status(wamid, dst)` using correct `id` field
- **`upsert_donna_user`**: role upgrade check missed 'support' role. Fixed to include 'support' alongside 'agent'
- **Default role**: all three places (`CREATE TABLE`, `INSERT`, `create_session`) defaulting to 'agent' → changed to 'support'
- **Login role**: was storing generic 'team' in session. Now looks up DB role first — manager/support/viewer stored correctly in session
- **`get_customers` claim lookup**: claimed conversations now show amber status in sidebar

## Current Scheduler
```
zatca(30min) | daily_summary(9am) | gl_snapshot(midnight) | health_check(6am)
collections_escalation(mon 8am) | suggestions_digest(mon 8:15am) | team_reminders(9:30am daily)
team_accountability(mon 8:30am) | monthly_pl(1st 9am) | refresh_coa(sun 11pm)
whatsapp_poll(5min-fallback) | email_check(30min) | delivery_check(10min) | takeover_expiry(30min)
sla_check(8:45am+5pm) | old_tickets_digest(mon 9am) | morning_briefing(8:30am)
escalation_check(5min) | eod_request(4:30pm KSA) | eod_summary(4:55pm KSA)
```

## Current Database Tables
```
gl_snapshots, zatca_alerts, conversation_history, scheduled_runs, daily_snapshots,
communication_log, suggestions, collections_tracker, chart_of_accounts,
team_interactions, ticket_assignments, team_pending_state, team_conversations,
daily_reports, eod_session_state, contacts, customer_conversations,
customer_escalations, sessions, whatsapp_conversations, processed_emails,
admin_conversations, push_subscriptions, donna_notifications,
donna_users, role_permissions, user_integrations, conversation_claims
```

## Milestone 9 — Role tools, handoff summary, coaching, enrichment (2026-04-28)

### 9.1 — Role-based tool gating in ask_claude ✅ 2026-04-28
Support/viewer roles get `TOOLS` minus 9 financial tools. System prompt suffix names the caller and their role.

### 9.2 — sender_role wired through /api/chat ✅ 2026-04-28
`session.get("role")` passed as `sender_role` to `ask_claude` so web UI chat respects RBAC.

### 9.3 — Customer auto-enrichment ✅ 2026-04-28
After each AI reply, regex scans inbound messages for name/company patterns and updates `contacts` table via `update_contact_enrichment`.

### 9.4 — Conversation handoff summary ✅ 2026-04-28
When agent claims a conversation, `_send_claim_handoff_summary` sends last 10 messages to their WhatsApp number.

### 9.5 — donna_users.whatsapp_number ✅ 2026-04-28
Schema migration adds column. `PATCH /api/users/{username}/whatsapp` lets agents set their own number. UserMgmtPanel shows WA field in edit mode.

### 9.6 — "Ask Donna" private coaching ✅ 2026-04-28
Support agents can ask Donna for guidance in the customer conversation view. Uses `/api/chat` in background; response visible only to the agent.

### 9.7 — Template guidance in OutboundWAComposer ✅ 2026-04-28
When 24h window is closed, composer shows guidance box with "Ask Donna for templates" button that queries approved templates via `/api/chat`.

## Pending / Next
- [ ] Per-user Gmail/calendar OAuth self-service flow (user_integrations table exists, needs OAuth dance)
- [ ] Support agent email workflow (email summaries + draft reply approve/reject in web UI)
- [ ] Contact enrichment from ERPNext Customer doctype (nightly sync)
- [ ] Full WhatsApp template API integration (list & send approved templates)

