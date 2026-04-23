# Donna — Session Log

---

## Session: 2026-04-16

### Summary
Initial planning session. No code was written this session.

### What was done
- Full capability audit of cloud_agent.py, erpnext_client.py, database.py
- Generated complete feature report covering all 13 on-demand tools, 3 scheduled jobs, and infrastructure
- Created DONNA_PLAN.md with full milestone roadmap (Milestones 1–4)
- Created SESSION_LOG.md (this file)
- Confirmed service running: cloud_agent.service active since 2026-04-15 23:01:21 UTC
- Logs clean — only Telegram polling activity, no errors

### What was completed
- DONNA_PLAN.md created at /opt/cloud_agent/DONNA_PLAN.md
- SESSION_LOG.md created at /opt/cloud_agent/SESSION_LOG.md

### What failed
- Nothing failed this session

### What is next
Start Milestone 1 in order:
1. Task 1.5 — Long message handling (quick win, affects all responses)
2. Task 1.1 — Smart daily summary (route through Claude, not raw data)
3. Task 1.3 — Collections escalation tracker (SQLite + weekly escalation)
4. Task 1.4 — Vendor bills / payables tools
5. Task 1.2 — Submit Sales Invoice (write operation, needs care)

---

## Session: 2026-04-16 (continued)

### Task 1.5 — Long message handling
- Added _split_message() helper: splits at newlines, chunks ≤4096 chars
- Added _send() wrapper: handles both Update (reply) and bot (send_message) callsites
- Updated handle_message, job_zatca_check, job_daily_summary to use _send()
- Deployed and verified service restart clean
- DONNA_PLAN.md updated: 1.5 marked done

### What is next
Task 1.1 — Smart daily summary (route through Claude with previous snapshot comparison)

### Task 1.1 — Smart daily summary
- Added daily_snapshots table to SQLite (snapshot_date, doc_type, doc_name, customer, amount, days_outstanding)
- Added save_daily_snapshot() and get_daily_snapshot() to database.py
- Added _build_daily_context() to cloud_agent.py: structures current + previous data, tags [NEW] entries and resolved ones, flags proforma age
- Rewrote job_daily_summary: routes context through Claude (direct API call, not ask_claude — no conversation history pollution), saves today's snapshot after sending
- Deployed and verified clean restart, daily_snapshots table confirmed in DB

### What is next
Task 1.3 — Collections escalation tracker

### Task 1.3 — Collections escalation tracker
- Added collections_tracker table: invoice_name, customer, amount, due_date, first_seen, last_seen, days_overdue, times_flagged, resolved, resolved_date
- Added upsert_collections(): increments times_flagged daily, marks resolved when invoice drops off overdue list
- Added get_active_escalations(): returns unresolved items sorted by times_flagged
- Added get_collections_escalations tool (on-demand)
- Added job_collections_escalation(): Monday 8am Riyadh, Claude-written digest, only fires if items flagged more than once
- Escalation levels: WATCHING (1-6), WARNING (7-13), ESCALATED (14+)
- Hooked upsert_collections into daily summary job
- Deployed clean, collections_tracker table confirmed

### What is next
Task 1.4 — Vendor bills / payables

### Task 1.4 — Vendor bills / payables
- Added get_overdue_payables() to erpnext_client.py: fetches Overdue Purchase Invoices, sorted by due_date
- Added get_purchase_invoices(days_back) to erpnext_client.py: fetches submitted PIs with supplier/amount/status
- Added get_overdue_payables tool: shows what we owe suppliers past due, with days overdue
- Added get_purchase_invoices tool: summary view — total billed, paid, outstanding, top 5 suppliers
- Deployed clean

### What is next
Task 1.2 — Submit Sales Invoice (complete proforma to submitted chain)

### Task 1.2 — Submit Sales Invoice + PDF
- Added submit_doc() to erpnext_client.py: calls frappe.client.submit
- Added convert_and_submit_proforma() to erpnext_client.py: make_sales_invoice + save + submit in one chain
- Added get_invoice_pdf() to erpnext_client.py: downloads PDF bytes from ERPNext print format endpoint
- Added submit_sales_invoice tool: submits an existing draft SI, confirms ZATCA will trigger
- Added convert_and_submit_proforma tool: proforma → submitted SI in one shot (requires confirmation)
- Added send_invoice_pdf tool: fetches PDF and sends as Telegram document — works for any submitted invoice
- Made _execute_tool async to support await bot.send_document()
- Threaded bot + chat_id through ask_claude() and handle_message() so PDF tool has Telegram context
- Deployed clean

### Milestone 1 COMPLETE — all 5 tasks done
### What is next
Milestone 2 — Self-Awareness & Suggestions Engine (start with 2.1 suggestions table)

### Milestone 2 — Self-Awareness & Suggestions Engine (2026-04-16)

#### Task 2.1 — Suggestions table
- Added suggestions table: id, description, reason, priority, date_noticed, status, implemented_date
- add_suggestion() with dedup (won't add same description twice while open)
- get_suggestions(status) sorted by priority then date
- update_suggestion(id, status, implemented_date)
- get_job_empty_streak(job_name, threshold) checks scheduled_runs history

#### Task 2.2 — Auto-logging triggers
- Unknown tool requested → High priority suggestion logged immediately
- Tool fails 3x in a row → High priority suggestion with last error
- Same question asked 3x → Medium priority suggestion (possible scheduled report candidate)
- GL snapshot saves 0 entries for 7 consecutive days → High priority suggestion
- _tool_failure_counts and _question_counts are module-level dicts (reset on restart)

#### Task 2.3 — Suggestion commands (3 new tools)
- get_suggestions: list open/dismissed/implemented suggestions
- dismiss_suggestion: mark by ID
- implement_suggestion: mark by ID with today's date

#### Task 2.4 — Weekly suggestions digest
- job_suggestions_digest: Monday 8:15am Riyadh, Claude-written digest
- Only fires if there are open suggestions
- Reminds Talha of dismiss/implement commands

### Milestone 2 COMPLETE
### What is next: Milestone 3 — Financial Intelligence Depth

### Milestone 3 — Financial Intelligence Depth (2026-04-16)

#### Task 3.1 — Historical GL trends
- get_gl_trends() and get_gl_monthly_totals() added to database.py
- Aggregates gl_snapshots by month and voucher_type
- Shows month-over-month arrows (up/down) for debit volume
- Returns "accumulating" message when no snapshot data exists yet
- get_gl_trends tool added to cloud_agent.py

#### Task 3.2 — Cash flow forecast
- get_cashflow_forecast tool: 30/60/90 day inflow buckets
- Uses overdue invoices, payment pattern lag per customer to estimate collection timing
- Proformas bucketed by % billed (>50% → 30 days, else 60 days)
- Subtracts overdue payables as outflow
- Shows net 30-day and 90-day position with Green/Red icon

#### Task 3.3 — Customer credit risk scoring
- get_customer_risk_scores tool: scores all active customers
- Red: >60d overdue OR avg pay >30d OR >2 invoices overdue
- Yellow: >30d overdue OR avg pay >15d OR 2 overdue
- Green: everything else
- 7 overdue invoices + 17 payment entries available for scoring

#### Task 3.4 — Monthly P&L digest
- job_monthly_pl_digest: 1st of every month 9am Riyadh
- Covers previous calendar month, both companies
- Claude writes in Donna's voice with commentary
- Registered in scheduler

### Milestone 3 COMPLETE
### Scheduled jobs: zatca(30min) | daily_summary(9am) | gl_snapshot(midnight) | collections_escalation(mon 8am) | suggestions_digest(mon 8:15am) | monthly_pl(1st 9am)
### What is next: Milestone 4 — Operations Expansion

### Milestone 4 — Operations Expansion (2026-04-16)

#### Task 4.1 — ZATCA retry
- retry_zatca_invoice() in erpnext_client.py: tries 4 known KSA compliance endpoints in order
- If all fail: self-logs a High suggestion and gives Talha the manual retry path
- retry_zatca_invoice tool added with write guard (requires confirmation)

#### Task 4.2 — Stock monitoring
- get_low_stock_items(warehouse) in erpnext_client.py: reads Bin doctype, compares actual_qty vs reorder_level
- get_low_stock_items tool added (returns graceful message if no stock — services company)
- Note: Bin count is currently 0 (BOT Solutions is a services company, no physical stock)

#### Task 4.3 — Instance health monitoring
- check_instance_health() in erpnext_client.py: ping + SSL expiry (via ssl/socket) + Scheduled Job Log failures + Donna disk usage (shutil)
- check_instance_health tool: on-demand full report
- job_health_check: daily 6am Riyadh, silent — only sends Telegram alert if something is wrong
- Auto-logs suggestions for SSL <30 days and disk >85%
- Smoke test results: reachable=True, SSL=41 days, disk=11.3% used, google_calendar.sync failing in bg

#### Task 4.4 — Multi-client foundation
- Added erpnext_instances dict to config.py with current instance as "metadaftr"
- list_erpnext_instances tool: shows configured instances
- Backward compatible — existing "erpnext" key unchanged

### Milestone 4 COMPLETE — All 4 milestones done
### Full scheduler:
# zatca(30min) | daily_summary(9am) | gl_snapshot(midnight) | health_check(6am daily)
# collections_escalation(mon 8am) | suggestions_digest(mon 8:15am) | monthly_pl(1st 9am)

---

## Session: 2026-04-16 (Session 2)

### Production Switch
- Switched primary ERPNext instance to helpdesk.botsolutions.tech
- Production API key/secret written directly to config.py (not in chat)
- UAT (metadaftr) kept under erpnext_instances as fallback
- All tools tested against production: overdue (9), proformas (6), ZATCA (7), GL (17), sales (12), payments (20), P&L, balance sheet, HD tickets (20), print formats confirmed
- SSL: 57 days on prod cert
- Default print formats set: Sales Invoice (AQT), Proforma Invoice (AQT)
- Note: Talha email written as talha@botsolutions.tech — user typed botsolutins.tech, assumed typo

### Communication Module — Phase A (Internal)
- Added communication_log table to SQLite
- Added log_communication() and get_communication_log() to database.py
- Added send_email() to erpnext_client.py via frappe.core.doctype.communication.email.make
- Added send_whatsapp() to erpnext_client.py via WhatsApp Message doctype (frappe_whatsapp app)
- Added send_email, send_whatsapp, get_communication_log tools to cloud_agent.py
- Whitelist enforced: only talha@botsolutions.tech and Baraa@botsolutions.tech for email
- Whitelist enforced: only +966546065347 and +966544272725 for WhatsApp
- All sends require confirmation + log to SQLite
- BLOCKER: Email requires ERPNext outgoing email account at Settings > Email Account — logged as suggestion #4
- WhatsApp: ready (frappe_whatsapp app installed, WhatsApp Message doctype confirmed working)

### What is next
- Configure ERPNext email account to unblock send_email
- Phase B — Client facing communication (dry-run, templates, send limits, opt-out tracking)


## Session: 2026-04-21

### Completed
- Investigated WhatsApp incoming DocType: confirmed 'WhatsApp Message' with type='Incoming', fields: name/from/message/creation/type/profile_name/message_type/message_id
- New database tables added: team_conversations, whatsapp_conversations, email_memory, processed_emails, client_profiles, sla_rules, team_members_db, wa_poll_state
- New database functions: log_team_conversation, get_team_conversation_history, update_wa_window, get_wa_poll_state, set_wa_poll_state, get_processed_email, mark_email_processed, get_email_memory, upsert_email_memory, init_sla_rules, sync_team_members_db
- SLA rules seeded at startup: Urgent(1h/4h), High(2h/8h), Medium(4h/24h), Low(8h/72h)
- team_members_db synced from config at startup (15 members)
- Incoming WhatsApp polling every 2 minutes (job_whatsapp_inbound_poll) — polls ERPNext WhatsApp Message DocType, filters by whitelist, alerts Talha via Telegram, posts ticket comments, sends queued messages when window reopens
- Email check every 30 minutes (job_email_check) — checks unread emails via Google, groups by thread, alerts Talha, tracks processed_emails to avoid duplicates
- SLA breach monitoring every 30 minutes (job_sla_check) — alerts on full breach and 80% warning threshold
- Morning team briefing at 8:30 AM Riyadh (job_morning_team_briefing) — per-member open ticket summary via WhatsApp
- ask_claude_team: loads last 10 team_conversations for context, also logs inbound to team_conversations and updates wa_window
- wa_send_safe: now logs outbound to team_conversations and calls update_wa_window

### Scheduler jobs (full list)
zatca(30min) | daily_summary(9am) | gl_snapshot(midnight) | health_check(6am daily)
collections_escalation(mon 8am) | suggestions_digest(mon 8:15am) | team_accountability(mon 8:30am)
team_reminders(9:30am daily) | monthly_pl(1st 9am) | refresh_coa(sun 11pm)
whatsapp_poll(2min) | email_check(30min) | sla_check(30min) | morning_briefing(8:30am)

### Pending
- Client profiles nightly sync from ERPNext (client_profiles table schema ready)
- Relationship health proactive alerts
- Full email reply approval flow via Telegram commands (draft reply / open ticket / ignore)
- Sentiment detection on client communications
- Auto-ticket creation from incoming WhatsApp/email
- Connect ERPNext email inbox via API (read incoming)

## Session: 2026-04-21 (continued — SLA fixes)

### SLA Alert Overhaul
- FIX 1: sla_check schedule changed from every 30 minutes to twice daily: 8:45 AM and 5:00 PM Riyadh
- FIX 2: Age filter added — tickets older than 90 days excluded from main SLA alerts
- FIX 2: New job job_old_tickets_digest (Monday 9:00 AM) — weekly digest of 90+ day open tickets titled 'Old Open Tickets Needing Closure'
- FIX 3: Assigned tickets now notify the agent directly via WhatsApp (wa_send_safe, 24h window enforced), not Talha
- FIX 3: Unassigned tickets only go to Talha digest — no spam for assigned ones
- FIX 4: sla_alerts_sent table added — dedup per ticket per 12 hours, prevents repeat alerts
- Scheduler log updated: sla_check(8:45am+5pm) | old_tickets_digest(mon 9am)

### Scheduler jobs (full list, updated)
zatca(30min) | daily_summary(9am) | gl_snapshot(midnight) | health_check(6am)
collections_escalation(mon 8am) | suggestions_digest(mon 8:15am) | team_accountability(mon 8:30am)
team_reminders(9:30am daily) | monthly_pl(1st 9am) | refresh_coa(sun 11pm)
whatsapp_poll(2min) | email_check(30min) | sla_check(8:45am+5pm)
old_tickets_digest(mon 9am) | morning_briefing(8:30am)

## Session: 2026-04-22 — WhatsApp Investigation + 5 Fixes

### Investigation Findings
- Critical bug found: log_team_conversation() was missing wa_message_name parameter — silently ignored, dedup never worked
- is_wa_message_processed() was defined twice in database.py (identical duplicate at lines 980 and 1046)
- _migrate_db() was also defined twice — second definition overrode first, dropped sla_alerts_sent creation
- send_whatsapp_template() missing use_template=1 and template fields — templates may not trigger Meta correctly
- WhatsApp Message DocType has 30+ fields: message_id, is_reply, reply_to_message_id, reference_doctype, conversation_id are key for threading
- 20 approved templates confirmed in ERPNext — chat_start-en, chat_initiation-en, hd_ticket_resolved, general_document_assignment, etc.
- whatsapp_conversations table had 6 contacts all window_active=1, last_inbound times valid
- Historical team_conversations showed same messages replayed every 2 minutes (the dedup bug in action)

### FIX 1 — Dedup Bug (RESOLVED, tested)
- Added wa_message_name=None parameter to log_team_conversation() signature
- Added sent_wa_message_name, delivery_status, conversation_thread_id parameters too
- Updated INSERT to include all new fields
- Removed second duplicate _migrate_db() definition (lines ~839)
- Removed entire duplicate function block at end of file (is_wa_message_processed x2, add_pending_context x2, etc.)
- TEST RESULT: Poll twice — second run: 0 processed, 2 deduped. wa_message_name stored correctly in new rows.

### FIX 2 — Delivery Status Tracking (IMPLEMENTED)
- New columns in team_conversations: sent_wa_message_name, delivery_status, conversation_thread_id
- wa_send_safe() now captures save_doc() return value and stores doc name as sent_wa_message_name
- check_delivery_status(doc_name) added to erpnext_client.py — GETs WhatsApp Message doc and returns status field
- job_delivery_check() added — runs every 10 minutes, checks untracked outbound messages
  - Updates delivery_status silently for delivered/read
  - Alerts Talha on Telegram for failed deliveries
- delivery_check(10min) registered in scheduler

### FIX 3 — Template Sending Fixed
- send_whatsapp_template() updated to include use_template=1 and template=template_name in doc
- This matches the structure of confirmed delivered template messages in ERPNext (general_document_assignment example)
- Chat window re-open flow: window closed → template sent → queued message stored → fires when they reply

### FIX 4 — Conversation Threading (IMPLEMENTED)
- conversation_thread_id column added to team_conversations
- get_or_create_thread_id(number, ticket_id): looks for existing thread in last 48h, creates new UUID otherwise
- wa_send_safe() now creates/reuses thread IDs when ticket_id is provided
- get_conversation_thread(number, ticket_id, limit): returns messages in chronological order
- get_team_conversation tool added: Talha can ask "show conversation with Khayam" or "what did we discuss with Arslan about #1781"

### FIX 5 — Template Awareness (IMPLEMENTED)
- whatsapp_templates table added to SQLite: template_name, doc_name, use_case, has_buttons, variables_count
- 20 approved templates seeded with use_case labels
- get_template_for_use_case(use_case) function added
- wa_send_safe() now accepts use_case parameter — picks correct template when window closed
  - Default (no use_case): chat_start-en (session opener)
  - use_case='ticket_assignment_team': general_document_assignment

### Scheduler jobs (full list, updated)
zatca(30min) | daily_summary(9am) | gl_snapshot(midnight) | health_check(6am)
collections_escalation(mon 8am) | suggestions_digest(mon 8:15am) | team_accountability(mon 8:30am)
team_reminders(9:30am daily) | monthly_pl(1st 9am) | refresh_coa(sun 11pm)
whatsapp_poll(2min) | email_check(30min) | delivery_check(10min)
sla_check(8:45am+5pm) | old_tickets_digest(mon 9am) | morning_briefing(8:30am)

### Known Issues / Remaining
- Historical team_conversations has ~100+ duplicate rows from pre-fix dedup failure (harmless, just history)
- chat_start-en has buttons — button press response comes as new Incoming message; reply handling covers this
- conversation_thread_id not retroactively assigned to old rows (would require ticket_reference data that was never stored)
- FIX 3 (template) not live-tested against a real device — ERPNext auto-saves and frappe_whatsapp hooks trigger on doc save; the general_document_assignment template confirms this mechanism works
- Client profiles nightly sync still pending (schema ready)

## Session: 2026-04-22 — Customer WhatsApp Module + Team Message Handler

### What was done
Full customer-facing WhatsApp module built end-to-end. All 10 steps completed.

### Database (database.py)
- Added 3 new tables: contacts, customer_conversations, customer_escalations
- _migrate_db() updated to create tables on existing installs
- New functions: get_contact_type, upsert_contact, get_contact, flag_contact,
  log_customer_conversation, get_customer_conversation_history, is_customer_message_processed,
  count_customer_messages_last_hour, create_customer_escalation, resolve_customer_escalation,
  take_customer_escalation, get_pending_customer_escalations, get_active_customer_escalation,
  get_all_customer_escalations, get_all_customers_with_last_message

### Cloud Agent (cloud_agent.py)
- detect_language(): Arabic/English detection via Unicode range U+0600-U+06FF
- handle_team_message(): ticket-only handler — ticket status/list/comment/create. 
  Non-ticket messages get polite redirect. Replaces ask_claude_team in webhook handler.
- handle_customer_message(): full customer flow — dedup, language detect, upsert contact,
  human-takeover check, rate limiting (10/hr), length limit (500 chars), anti-exploitation,
  ticket intent + lookup, general inquiry via Claude Haiku, topic guardrail
- _send_customer_reply(): send WhatsApp + log to customer_conversations
- trigger_escalation(): create escalation, notify Talha via Telegram + assigned team via WA
- job_escalation_check(): runs every 5 minutes, auto-creates ERPNext tickets for pending 
  escalations >15 min old, notifies customer + Talha
- Poll handler modified: unknown numbers (not in whitelist) → routed to handle_customer_message()
- Telegram 'take PHONE' command: marks escalation as taken, notifies customer, shows agent name
- Escalation job registered: escalation_check(5min) in scheduler

### Anti-exploitation guardrails
- Prompt injection pattern list (EN+AR)
- Rate limiting: 10 messages/hour per customer
- Message length cap: 500 characters
- Topic guardrail: blocks responses leaking internal doc names

### web_api.py
- GET /api/customers: returns contacts table with last message + escalation color
- GET /api/customers/{phone}/conversation: returns customer_conversations table
- GET /api/escalations: all active escalations
- POST /api/escalations/{id}/take: marks escalation taken, notifies customer via WA

### Donna.html
- CUSTOMERS_MOCK replaced with live /api/customers polling (every 30s)
- /api/escalations polled every 30s for flag status
- Customer conversation: real-time poll of /api/customers/{phone}/conversation every 10s
- Intervene button: POSTs to /api/escalations/{id}/take, then POSTs to /api/tools/send-whatsapp
- liveCustomers/liveCustomerMsgs/escalations React state replaces all mock data

### Config (config.py)
- escalation_timeout_minutes: 15
- customer_rate_limit_per_hour: 10
- customer_max_message_length: 500

### Scheduler jobs (full list, updated)
zatca(30min) | daily_summary(9am) | gl_snapshot(midnight) | health_check(6am)
collections_escalation(mon 8am) | suggestions_digest(mon 8:15am) | team_accountability(mon 8:30am)
team_reminders(9:30am daily) | monthly_pl(1st 9am) | refresh_coa(sun 11pm)
whatsapp_poll(2min) | email_check(30min) | delivery_check(10min)
sla_check(8:45am+5pm) | old_tickets_digest(mon 9am) | morning_briefing(8:30am)
escalation_check(5min)

### Verified working
- DB tables created: contacts ✓, customer_conversations ✓, customer_escalations ✓
- /api/customers returns real data with status_color (green/orange/red)
- /api/customers/{phone}/conversation returns real conversation history
- /api/escalations returns active escalations
- Service restarted clean, no errors
- Frontend at http://165.232.114.90:8080 loads real customer data

### What is next
- Test live customer message flow (send WA from unknown number → appears in sidebar)
- Test escalation auto-ticket creation (temporarily reduce timeout to 1 min)
- Wire handle_customer_message for queued messages (window closed → template → queue)
- Client profiles nightly sync (schema ready in DB)

---

## Session: 2026-04-23

**Goal:** Set up proper project structure, auth system, team message routing fix, GitHub prep.

**Completed:**

### FIX 1 — Abdul Malik / Team Message Routing
- Added `normalize_phone(phone)` function (strips spaces/dashes, ensures + prefix)
- Poll handler whitelist now uses `normalize_phone()` for consistent lookup
- Replaced "I didn't catch which ticket" fallback with `handle_team_message()` call
- General team messages now get intelligent responses instead of ticket confusion

### FIX 2 — Real ERPNext Authentication
- Added `sessions` table to cloud_agent.db
- `create_session()`, `get_session()`, `delete_session()` helpers in database.py
- `POST /api/auth/login` — calls ERPNext login API, issues Bearer token
- `GET /api/auth/me` — returns current user (username, role)
- `POST /api/auth/logout-token` — invalidates session

### FIX 3 — Frontend Login Wired
- `fetchApi` replaced by `authFetch` (adds `Authorization: Bearer <token>`)
- Login form hits `/api/auth/login`, stores `{name, token, role}` in localStorage
- Token verified via `/api/auth/me` on app load, shows Loading… until checked
- Both logout buttons call server to invalidate session

### FIX 4 — Role-Aware UI
- Financial and System tool sections marked `adminOnly: true`
- Team role users only see Operations and Communication tools

### FIX 5 — Config Update
- Added `admin_users: ["talha@botsolutions.tech", "Administrator"]` to config.py

### Project Structure
- `logs/` directory with rotating file handlers (app.log, error.log, whatsapp.log)
- `docs/ARCHITECTURE.md` — full message flow + DB schema docs
- `docs/KNOWN_ISSUES.md` — open issues and technical debt tracker
- `README.md` — project overview and operations guide
- `config.example.json` — template for new deployments
- `.gitignore` — excludes config.py, *.db, logs/, *.bak
- Git repo initialized, initial commit (13 files, 10815 lines)

**Service status:** Running — `systemctl is-active cloud_agent` = active

**Next:** Add GitHub remote (need repo URL from Talha) and push

---

## Session: 2026-04-23 (continued) — Webhook path team_conversations logging

**Fix:** `_process_whatsapp_message()` (webhook handler path) was not logging team
member inbound messages or outbound replies to `team_conversations`. This meant
messages from Al Baraa, Abdul Malik, and others sent via webhook (not the poll
handler) never appeared in the dashboard UI team conversation view.

**Changes to `cloud_agent.py` `_process_whatsapp_message()` team `else:` branch:**
- Added `db.log_team_conversation(..., 'inbound', ...)` immediately after routing to team path
- Added `db.update_wa_window(sender, 'inbound')` to track 24h window
- Changed `erp.send_whatsapp()` to capture return value (`result`)
- Added `db.log_team_conversation(..., 'outbound', ...)` after sending reply
- Added `db.update_wa_window(sender, 'outbound')` after sending reply

**Root cause:** The poll path (`job_whatsapp_inbound_poll`) was already logging
correctly, but the webhook path (`_process_whatsapp_message`) was only logging to
`communication_log` — not to `team_conversations` which the UI reads.

---

## Session: 2026-04-23 (continued) — Double reply, team panel, intervene double-log

### BUG 1: Double reply to team members
Webhook handler (`_process_whatsapp_message`) had no dedup — it fired immediately
on receipt. Then 2 min later `job_whatsapp_inbound_poll` processed the same message
again (it has wa_name-based dedup but the webhook fires before the wa_name is known).
**Fix:** `handle_whatsapp_webhook` now checks `access` from whitelist — if `team`,
returns 200 immediately without spawning `_process_whatsapp_message`. Team messages
are fully handled by the poll job which has proper dedup. Only `admin` (Talha) goes
through the webhook processing path.

### BUG 2: Team members missing from left panel
`/api/team/members` only returned members who had a record in `whatsapp_conversations`
table (from 24h window tracking). Members like Abdul Malik who had never had a window
record showed with no last_message, or not at all if the frontend filtered them.
**Fix:** Endpoint now also queries `team_conversations` for `MAX(timestamp)` per number
and uses that as fallback for `last_message`. All config `team_members` are always
returned regardless of whether they have a `whatsapp_conversations` record.

### BUG 3: Intervene send logged twice to customer_conversations
Customer intervene send was POSTing to both:
1. `/api/tools/send-whatsapp` with `intervention:true` (which already logs to customer_conversations)
2. `/api/customers/{phone}/log-human-message` (which logged again = duplicate)
**Fix:** Removed the second `log-human-message` fetch from the intervene send flow.
The `send-whatsapp` endpoint's `intervention:true` path is sufficient — it logs
to `customer_conversations` via `db.log_customer_conversation()`.

---

## Session: 2026-04-23 (continued) — Live team panel + chat persistence

### FIX 1: Team panel loads from API (all 15 members)
- Replaced hardcoded `TEAM` constant (2 members) with `TEAM_STATIC` (fallback only)
- Added `liveTeam` + `teamIdMap` state initialised from `TEAM_STATIC`
- New `useEffect` polls `/api/team/members` on mount and every 60s
- Builds `id` from `name.toLowerCase().replace(/\s+/g,'')` — e.g. Abdul Malik → `abdulmalik`
- Builds `teamIdMap` dynamically so team conversation poll works for all members
- `Sidebar` now receives `liveTeam` prop and renders all live members
- `isTeamThread` and `activeMember` now use live `teamIdMap` / `liveTeam`
- `/api/team/members` verified: returns all 15 members, `last_message` populated from `team_conversations` fallback

### FIX 2: Chat history persists within browser session
- `threads` state now initialises from `sessionStorage.getItem('donna-threads')` if present
- `addMessage` callback writes updated threads to `sessionStorage` on every message
- Survives page refresh within same browser session; cleared when tab is closed
- Only restores if `donna.length > 1` (skips the hardcoded welcome message)

---

## Session: 2026-04-23 (continued) — Conversational team AI, collapsible sidebar, message persistence

### FIX 1: Team WhatsApp replies now use conversational Claude Haiku
- Added `ask_claude_team_conversational()` function before `handle_team_message()`
- Loads last 6 messages from `team_conversations` as context for each reply
- System prompt allows: work, tickets, ERPNext, coordination. Refuses: private emails, salary/payroll, client financials
- Replies capped at 200 tokens for WhatsApp-appropriate length
- Falls back to "Got your message. I'll make sure Talha sees this." on API error
- STEP 5 in poll handler now calls this instead of the ticket-only `handle_team_message()`

### FIX 2: Team section in sidebar is now collapsible
- Added `TeamSection` React component (collapsed by default, shows member count)
- Chevron rotates 180° when expanded; member list scrolls at max 280px height
- Sidebar renders `<TeamSection/>` instead of inline `TEAM.map`

### FIX 3: Intervention messages no longer disappear on next poll
- Added `lastApiMsgCountRef` to track per-thread API message count
- Team conversation poll now merges instead of replacing: only updates when API count increases
- When count unchanged, preserves current thread state (keeps optimistic intervene messages)
- When count increases, appends local `asHuman` messages not yet reflected in API
- Poll dependency array updated to `[activeThread, teamIdMap]`

---

## Session: 2026-04-23 (continued) — Webhook path conversational AI for team

**Fix:** `_process_whatsapp_message()` webhook path was still calling `handle_team_message()`
(ticket-only, returns "I can only help with tickets"). Now calls `ask_claude_team_conversational()`
instead — same as the poll path. Both paths now give instant, natural conversational replies.

**Also removed:** unused `member = _TEAM_LOOKUP.get(sender)` / fallback dict — not needed
since `ask_claude_team_conversational` only uses `sender_number` and `sender_name`.

**Result:** All team member WhatsApp messages — whether received via webhook (instant) or
poll (2 min) — now get full conversational Claude Haiku responses with conversation history.

---

## Session: 2026-04-23 (continued) — Instant team replies via webhook

**Root cause:** Webhook handler had an early-return for team members (`access == 'team'`)
added in the Bug 1 fix session. This meant all team messages waited for the 2-min poll
cycle instead of getting instant replies. The early-return was added to prevent double
replies, but we now handle that with proper hash-based dedup instead.

**Fix 1 — Removed early-return:** `handle_whatsapp_webhook` no longer skips team members.
All whitelisted numbers (admin + team) go through `_process_whatsapp_message`.

**Fix 2 — Hash dedup in webhook:** When the webhook logs the inbound to `team_conversations`,
it generates a dedup key: `wh_` + MD5(`sender:message:YYYYMMDDHHMM`)[:16]. If
`log_team_conversation` returns `False` (unique constraint hit), returns immediately —
message was already processed.

**Fix 3 — Hash dedup in poll:** STEP 5 in `job_whatsapp_inbound_poll` computes the same
hash for the current minute AND the previous minute (covers poll arriving 1+ min after
webhook). If either hash key is already in `team_conversations`, the poll skips the AI
call entirely and continues.

**Verified:** Test webhook call → `WhatsApp in from Abdul Malik` logged at 15:21:42,
`WhatsApp reply sent` at 15:21:45 — **3 seconds end-to-end**.
