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

---

## Session: 2026-04-24 — EOD Report System + SSL + PWA

### EOD Daily Report System

**database.py:**
- Added `daily_reports` table — stores member name, date, summarized report
- Added `eod_session_state` table — tracks active collection conversations
- Added 6 helpers: `get_eod_session`, `set_eod_session`, `clear_eod_session`,
  `save_daily_report`, `get_daily_reports`, `get_member_report_history`

**cloud_agent.py:**
- `_build_eod_opener()` — opener message for check-in
- `_handle_eod_conversation()` — intercepts WhatsApp replies during active EOD session,
  runs 2-turn Claude Haiku collection, finalizes when done
- `_finalize_eod_report()` — summarizes transcript into bullets, saves to DB
- `job_eod_report_request` — **16:45 KSA (13:45 UTC)**: sends opener to all team members
- `job_eod_summary` — **18:30 KSA (15:30 UTC)**: compiles digest, sends to admin WhatsApp
- `get_eod_reports` tool — Talha can ask "show today's EOD reports" in Telegram

**web_api.py + Donna.html:**
- `GET /api/reports/daily?date=YYYY-MM-DD` — today's reports
- `GET /api/reports/member/{whatsapp}` — per-member history (last 10)
- `ReportsSection` collapsible in sidebar below Team
- `ReportDetailPanel` — clicking a member shows full report history with dates

### STEP 1: SSL via Caddy

Installed Caddy v2.11.2 on server. Configured reverse proxy for
`donna.botsolutions.tech` with automatic Let's Encrypt SSL (HTTP-01 challenge).
Opened ports 80/443. Certificate provisioned automatically on first start.

**Verified:** `https://donna.botsolutions.tech/` returns HTTP 200. HSTS,
X-Content-Type-Options, X-Frame-Options, Referrer-Policy headers all active.

### STEP 2–4: PWA Manifest + Service Worker + Icons

- `/manifest.json` — installable app definition (name, icons, theme, standalone display)
- `/sw.js` — cache-first SW, API calls network-first, offline fallback to cached shell
- `/icon.svg` — dark rounded-rect with teal "D" glyph
- `/icon-192.png` — redirects to SVG
- All PWA meta tags added to `<head>`: apple-mobile-web-app-capable,
  apple-mobile-web-app-status-bar-style, theme-color, manifest link, apple-touch-icon
- SW registered in `window.load` event

**To install on iPhone:** Safari → `https://donna.botsolutions.tech` → Share → Add to Home Screen

### STEP 5: Mobile CSS Overhaul

- Safe area insets (`env(safe-area-inset-bottom)`) for notch/home indicator devices
- Sidebar: cubic-bezier(0.4,0,0.2,1) smooth slide-in, max-width 320px cap
- Tools panel: bottom sheet, 75vh/600px max, cubic-bezier transitions
- Bottom nav: proper padding for home indicator bar
- Input area: `padding-bottom: calc(8px + env(safe-area-inset-bottom))`

### STEP 6: Back Button + Tools Drag Handle

- `isMobile` state (window.innerWidth <= 768) with resize listener
- Header button: shows "← Back" when on mobile AND in a non-Donna thread;
  otherwise shows hamburger
- Tools panel: drag handle pill at top (tap to close)

### NEXT

Test on real iPhone/Android:
1. Go to `https://donna.botsolutions.tech` in Safari
2. Share → Add to Home Screen
3. Verify: standalone display, teal status bar, safe area padding, back button



---

## Session: 2026-04-26 — EOD Report Fixes

**Root cause:** EOD reports only saved when triggered by the scheduled job at 16:45 KSA
(which sets eod_session_state first). When team members manually sent 'eod' or 'daily
report' messages outside the scheduled window, ask_claude_team_conversational handled
them as normal conversation — no session was started, so nothing was saved.

**FIX 1 — Backfilled Imran 2026-04-24 report:**
- Resolved 4horizon print format issue (ticket #1792) — completed
- Aldallow warehouse data migration — in progress, on track
- Plan for tomorrow: complete aldallow warehouse data

**FIX 2 — Manual EOD keyword trigger:**
ask_claude_team_conversational now checks for EOD keywords before normal path:
eod, end of day, daily report, my report, work report, eod report, day report.
If detected with no active session: creates eod_session_state (collecting) and
replies with check-in prompt — same flow as scheduled job.

**FIX 3 — get_eod_reports tool fallback:**
When daily_reports is empty for a date, the tool now queries team_conversations
for EOD-related messages and reports who sent them, noting reports were handled
conversationally but not saved (now fixed going forward).


---

## Session: 2026-04-26 (continued) — daily_reports Schema Fix

**Problem:** daily_reports table created with minimal schema (id, whatsapp_number,
member_name, report_date, report_text, created_at). Code and frontend expected
status, raw_conversation, submitted_at, prompted_at columns. No UNIQUE constraint,
so ON CONFLICT dedup did nothing.

**FIX 1 + 3 — Live migration:**
Added missing columns via ALTER TABLE (status DEFAULT submitted, raw_conversation,
submitted_at, prompted_at). Backfilled submitted_at=created_at for existing rows.
Created UNIQUE INDEX idx_dr_date_wa ON daily_reports(report_date, whatsapp_number).

**FIX 2 — database.py:**
- Updated CREATE TABLE in init_db to include all columns + UNIQUE constraint
- save_daily_report: now takes raw_conversation+status params, uses ON CONFLICT upsert
- Added log_daily_report_prompt: inserts prompted row before report arrives
- Added is_pending_eod_report: checks if prompt sent but report not submitted
- get_daily_reports: adds whatsapp_number AS member_whatsapp alias, COALESCE(status)
- get_member_report_history: same alias, filters empty prompted rows

**FIX 4 — cloud_agent.py:**
- job_eod_report_request now calls db.log_daily_report_prompt on send,
  so each member has a prompted row before they reply

**Verified:**
- All 4 reports (Ahmad Bilal, Mohammad Amir, Mohammad Imran x2) returned correctly
- member_whatsapp field present in all API responses
- ON CONFLICT dedup works (tested duplicate insert replaced, not duplicated)


---

## Session: 2026-04-26 — HTTPS Webhook + Content Dedup + 60s Poll

**PART 1 — Caddy routing:**
Added /whatsapp-incoming and /webhook-health routes to Caddyfile, both
pointing to port 8765 (aiohttp webhook server). All other traffic continues
to port 8080 (FastAPI dashboard). Caddy reloaded with no downtime.

**PART 2 — ERPNext webhook updated programmatically:**
Used ERPNext REST API (PUT /api/resource/Webhook/Donna WhatsApp Inbound)
to update request_url from http://165.232.114.90:8765/whatsapp-incoming
to https://donna.botsolutions.tech/whatsapp-incoming.
Verified: URL updated, Enabled: 1.

**PART 3 — Poll reduced from 2 min to 60s:**
job_whatsapp_inbound_poll now runs every 60 seconds. Webhook is primary
(instant), poll is fallback for anything missed. Log line updated to
whatsapp_poll(60s-fallback).

**PART 4+5 — Content+time dedup (root cause fix):**
Root cause: webhook stored wh_+MD5 hash as wa_message_name, poll stored
real ERPNext doc name (e.g. WA-MSG-2026-00123). These never matched on
the UNIQUE constraint, so the same message was processed twice.
Fix: new db.is_team_message_recently_processed(number, content, 3min) and
is_customer_message_recently_processed() functions check content+timestamp
window instead of doc name. Poll now checks these before calling Claude.
If content dedup hits, poll still registers the ERPNext doc name so future
polls skip it via the cheaper is_wa_message_processed check.

**PART 6 — Cleanup:**
Deleted 85 duplicate team_conversations records from before 2026-04-22
(pre-dedup era, wa_message_name=NULL, kept MIN(id) per member+content).

**Verified:**
curl -X POST https://donna.botsolutions.tech/whatsapp-incoming
→ WhatsApp in from Abdul Malik logged
→ Reply sent in 4 seconds
Full HTTPS path confirmed working end-to-end.


---

## Session: 2026-04-26 — Mobile Layout Critical Fixes

**Problem 1 (double sidebar div):** Sidebar component returned a div with
className='sidebar' id='sidebar-el' — same as the outer wrapper in App JSX.
This created two nested .sidebar divs, CSS applied to both, causing double-width
and broken fixed positioning on mobile.
Fix: Sidebar now returns plain flex div with height:100%/overflow:hidden.

**Problem 2 (isMobile via window.innerWidth):** window.innerWidth doesn't
always match CSS media queries (different scroll bar handling, viewport meta).
Fix: replaced with window.matchMedia('(max-width:768px)') listener. Also added
visualViewport resize/scroll handler to track --keyboard-offset for keyboard avoidance.

**Problem 3 (.main-area width):** On mobile, sidebar is position:fixed (out of flow)
but .main-area still only got flex:1 of .app-body. Without the sidebar column
consuming space, .main-area should take full width.
Fix: .main-area{width:100vw} and .chat-col{width:100%;border-right:none;min-width:0}
added to mobile media query.

**Problem 4 (overlay on desktop):** .overlay.open showed on desktop when
sidebarOpen=true (e.g. if state was stale). Added @media(min-width:769px) rule
with display:none !important to prevent this entirely.

**Problem 5 (drag handle on desktop):** Tools panel drag handle was always
rendered (no guard). Wrapped in {isMobile&&...}.

**Problem 6 (dvh):** html/body/#root and .app-shell now use height:100dvh as
progressive enhancement alongside 100vh for Safari mobile viewport correctness.

**Also improved:**
- .mob-nav-btn: added position:relative for future badge support
- .mob-nav-btn svg: opacity:0.7/1 for active state visual feedback
- status-bar and header-user-pill: display:none !important on mobile
- sidebar CSS in mobile: added display:flex;flex-direction:column for consistency

---

## Session: 2026-04-28 — Dedicated Meta App, RBAC, Role System, Web UI Overhaul

### Context
Continued from previous context-limit session. All work from the prior session (WhatsApp
real-time webhook, identity fix, RBAC foundation) was already deployed. This session
completed the full role system and web UI overhaul based on Talha's confirmed plan.

---

### Part 1 — Dedicated Donna Meta App

**Problem:** Donna was sharing the ERPNext Meta app, which meant webhook events went to
ERPNext first and were fanned out to Donna. Real-time WhatsApp was not possible this way.

**Solution:** Talha created a separate Meta app dedicated to Donna.

**Changes:**
- `config.py`: Updated `meta_whatsapp` block — new access_token, app_id (4557236414522831), api_version v25.0
- `web_api.py`: Removed all ERPNext fan-out code (`_ERPNEXT_WH_URL`, `_forward_to_erpnext` coroutine)
- `web_api.py`: Clean `/whatsapp-incoming` POST handler — verify → ACK 200 → dispatch to handlers
- Caddy: Simplified to route all traffic to localhost:8080 (removed split /whatsapp-incoming → 8765)
- Webhook URL configured in Meta: https://donna.botsolutions.tech/whatsapp-incoming
- Verified: test message received and processed in real-time

---

### Part 2 — Identity Fix

**Problem:** All web chat users appeared as "Talha" to Donna because `/api/chat` hardcoded `sender_name="Talha"`.

**Fix:**
- Added `_display_name_for(username)` helper in web_api.py
- Checks: donna_users DB → team_members config → email local-part parse
- Login endpoint now returns `display_name` in response
- `/api/auth/me` returns `display_name`
- Frontend extracts `display_name` from login response; uses for initials and sidebar header

---

### Part 3 — RBAC Foundation + donna_users

**Changes (database.py):**
- Added `donna_users` table: id, username, display_name, role DEFAULT 'support', is_active, created_at, last_login
- `_ensure_donna_users()` called at import time (idempotent)
- `upsert_donna_user()`: called on every login — updates last_login, upgrades role if appropriate (never silently downgrades)
- `get_donna_user()`, `list_donna_users()`, `update_donna_user_role()`, `update_donna_user_name()`, `deactivate_donna_user()`, `activate_donna_user()`

**Changes (web_api.py):**
- User management endpoints (all require admin):
  - `GET /api/users` → list with ROLE_LABELS
  - `PATCH /api/users/{username}/role`
  - `PATCH /api/users/{username}/name`
  - `PATCH /api/users/{username}/deactivate`
  - `PATCH /api/users/{username}/activate`
- `POST /api/users` — pre-create user before first login
- `VALID_ROLES = {"admin", "manager", "support", "viewer"}`

**Changes (Donna.html):**
- `UserMgmtPanel`: users grouped by role, inline name editing, role dropdown, enable/disable toggle
- "User Management" in System tools nav
- "Add User" form with username/email, display name, role selector

---

### Part 4 — EOD Schedule Fixed to KSA Times

**Root cause:** Scheduler has `timezone="Asia/Riyadh"` — `hour=` values are already KSA.
Existing crons (`hour=13, minute=45` and `hour=15, minute=30`) fired at 1:45 PM and 3:30 PM KSA.

**Fix:**
- EOD request: `hour=16, minute=30` (4:30 PM KSA)
- EOD summary: `hour=16, minute=55` (4:55 PM KSA)
- Docstrings corrected, startup log updated

---

### Part 5 — Role System (3 roles, dynamic permissions)

**Database changes:**
- `role_permissions` table: (role, permission, granted) — PRIMARY KEY (role, permission)
- `user_integrations` table: per-user OAuth tokens for Gmail/Calendar
- `conversation_claims` table: human agent conversation claiming
- contacts table: added status, email, need_category, enriched_name, enriched_at, donna_paused, ticket_count
- Role `agent` renamed → `support` in all DB records, defaults, and code

**15 permissions seeded with correct defaults per role:**
```
view_financials, view_reports, manage_users, manage_roles, manage_settings,
view_customers, chat_customers, send_whatsapp, claim_conversation,
view_eod_summary, view_calendar, view_email, escalate_tickets,
view_team_chat, send_email_draft
```

**New DB helpers:**
- `get_role_permissions(role)`, `get_all_role_permissions()`, `set_role_permission(role, perm, granted)`
- `has_permission(username, permission)` — looks up via donna_users role → role_permissions
- `save_user_integration()`, `get_user_integration()`, `list_user_integrations()`, `remove_user_integration()`
- `claim_conversation()`, `release_conversation()`, `get_conversation_claim()`, `get_all_claims()`
- `update_contact_enrichment(phone, **kwargs)`
- `create_donna_user_manual(username, display_name, role)`

**New web_api.py endpoints:**
- `GET /api/permissions` — full role permission matrix (admin only)
- `PATCH /api/permissions` — toggle one permission flag for a role (admin only)
- `GET /api/auth/permissions` — current user's permissions dict (for frontend gating)
- `POST /api/customers/{phone}/claim` — claim conversation (requires claim_conversation perm)
- `POST /api/customers/{phone}/release` — release claim (claimer or admin)
- `GET /api/conversations/claims` — all active claims
- `POST /api/whatsapp/send` — outbound message to any number (requires send_whatsapp perm)
- `GET /api/whatsapp/check-window/{phone}` — 24h messaging window status
- `PATCH /api/customers/{phone}/enrich` — update enrichment fields
- `require_manager` dependency (admin + manager)
- `_check_permission(session, permission)` helper (raises 403 if not permitted)

**Login flow fixed:**
- Now looks up DB role BEFORE creating session — correct role stored in session token
- Session TTL: 24h → 7 days
- Permissions fetched from `/api/auth/permissions` immediately after login and stored in `loggedIn` state

**P&L Overview endpoint:** now requires admin auth

---

### Part 6 — Web UI: Role Permissions Panel

**`RolePermissionsPanel` React component:**
- Admin-only panel; toggle switches for manager/support/viewer columns
- One row per permission with human-readable label + technical name
- Instant save via PATCH /api/permissions; reloads on change
- Admin column not shown (always full, not editable)
- "Role Permissions" added to System tools nav

---

### Part 7 — Web UI: Outbound WhatsApp Composer

**`OutboundWAComposer` React modal:**
- Phone number input with `onBlur` → GET /api/whatsapp/check-window
- 24h window indicator: green (free text OK) / amber (window closed warning)
- Message textarea with character counter
- Send via POST /api/whatsapp/send
- "+ New" button added to customers sidebar

---

### Part 8 — Web UI: Conversation Claiming

**`ClaimButton` React component (in conversation header):**
- Polls GET /api/conversations/claims every 10s
- Shows: "Claim" button if unclaimed, "✍️ [Name] handling" + Release if claimed
- Admin can release any claim; others can only release their own
- Customer card in sidebar shows claimer name badge
- Claimed conversations: amber status bar in sidebar, `donna_paused=1` on contact

**cloud_agent.py changes:**
- `handle_customer_message` now checks `db.get_conversation_claim(sender_number)` first
- If claimed: logs inbound message but returns without AI response
- This gives the human agent full message visibility without Donna interfering

---

### Part 9 — EOD Summary for Managers

- `job_eod_summary` now fetches all donna_users with role='manager' and is_active=1
- Matches their username (email) against team_members config to find WhatsApp number
- Sends same full EOD digest to all managers in addition to admin
- Haider (once added as manager) will receive the 4:55 PM summary automatically

---

### Part 10 — Business Hours Helper

- `_is_business_hours()` — returns True if KSA time is Sun–Thu 10am–5pm (Fri/Sat off)
- `_business_hours_message(lang)` — OOH message in English or Arabic
- Not yet enforced automatically — wired in, ready to activate in customer message handler

---

### Part 11 — Bug Fixes Found in Code Review

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | cloud_agent.py | `_dispatch_inbound_whatsapp`: `set(whitelist_list_of_dicts)` → `TypeError: unhashable type: 'dict'` | Set comprehension: `{w["number"] for w in whitelist_list if isinstance(w, dict)}` |
| 2 | cloud_agent.py | Same function: `_process_whatsapp_message(phone, text, msg_id, sender_name)` — wrong arg count/order | Fixed to `(phone, sender_name, text)` |
| 3 | cloud_agent.py | `_fastapi_wa_dispatch` calls nonexistent `_handle_delivery_status(phone, status)` | Replaced with inline `db.update_delivery_status(wamid, dst)` using correct `id` field |
| 4 | database.py | `upsert_donna_user` role upgrade check: `existing["role"] in ("agent", "viewer")` — missed 'support' | Added 'support' to check |
| 5 | database.py | Default role in INSERT and CREATE TABLE: `'agent'` | Changed to `'support'` everywhere |
| 6 | web_api.py | Login stored generic `'team'` in session regardless of DB role | Now looks up DB role first, stores correct role |
| 7 | web_api.py | `get_customers`: claimed contacts had no status change in sidebar | Claimed contacts now show `status_color = 'orange'` (amber) |
| 8 | web/Donna.html | `liveCustomers` mapping didn't include `claimed_by`/`claimed_by_name` | Added both fields to mapping |
| 9 | web/Donna.html | TOOLS Financial section was `adminOnly` — managers blocked from their own reports | Changed to `managerOnly` (admin + manager) |
| 10 | web/Donna.html | `ROLE_ORDER` in UserMgmtPanel still had `'agent'` | Changed to `'support'` |

---

### Commits this session
```
4577229 feat: RBAC user management, identity fix, WhatsApp webhook via FastAPI
0fb5dd8 feat: switch to Donna dedicated Meta app, remove ERPNext fan-out
77d8f49 fix: EOD schedule corrected to KSA times + server timezone set to Asia/Riyadh
28f0252 feat: role system, permissions, conversation claiming, outbound WA, CRM improvements
88342f4 fix: bug fixes across all files from code review
```

### Service state
- `cloud_agent.service` — active (running), no errors
- FastAPI webhook handler registered at startup
- Web UI WhatsApp sender registered at startup
- All 20 scheduler jobs active

### What is next
- [ ] Business hours enforcement in customer message handler
- [ ] Per-user Gmail OAuth self-service flow
- [ ] Per-user email polling + draft reply approval
- [ ] Customer profile auto-enrichment (soft collection by Donna during conversation)
- [ ] Role-based Donna system prompt injection (different context per role)
- [ ] "Ask Donna" private coaching in conversation view
- [ ] Outbound WhatsApp template selector (closed 24h window)
- [ ] Contact enrichment from ERPNext Customer doctype

---

## Session: 2026-04-28 (Part 2 — continuation)

### Summary
Implemented all remaining items from the feature audit list.

### What was done

**cloud_agent.py**
- `sender_role: str = "admin"` parameter added to `ask_claude()`
- Role-based tool gating in `ask_claude`: support/viewer roles cannot access `_FINANCIAL_TOOLS` (9 financial tool names excluded from `TOOLS` list passed to Claude)
- Role-based system prompt suffix: each call to Claude includes the caller's name and role
- Auto-enrichment after customer AI reply: regex scans last 6 inbound messages for name/company patterns and calls `db.update_contact_enrichment()` if found
- `_send_claim_handoff_summary(agent_username, phone)`: async helper that sends WhatsApp summary of last 10 messages to the claiming agent when they take over a conversation. Falls back to `CONFIG.team_members` by email match if no `donna_users.whatsapp_number` set

**database.py**
- `ALTER TABLE donna_users ADD COLUMN whatsapp_number TEXT` migration (runs on startup, idempotent)
- `set_donna_user_whatsapp(username, whatsapp_number)` function

**web_api.py**
- `PATCH /api/users/{username}/whatsapp` — set agent's WhatsApp number (self or admin)
- `sender_role=session.get("role")` wired through `/api/chat` → `ask_claude()`
- `PATCH /api/customers/{phone_number}/claim` now triggers `_send_claim_handoff_summary` in background task

**web/Donna.html**
- `OutboundWAComposer`: when 24h window is closed, shows detailed guidance box with "Ask Donna for templates" button that queries `/api/chat` and populates the message field
- "Ask Donna privately" button in customer conversation input area: collapses inline coaching panel where support agents type a question and get Donna's guidance (not visible to customer)
- `UserMgmtPanel`: WhatsApp number field appears in edit mode for each user; PATCH `/api/users/{username}/whatsapp` on blur

### Bug fixes this session
| # | File | Problem | Fix |
|---|------|---------|-----|
| 1 | cloud_agent.py | `description=f"..."` with literal newline in OOH ticket block | Converted to string concatenation with `\\n` |
| 2 | cloud_agent.py | Regex `[,.\\n]` had literal newline injected by patch script | Fixed by line-merge script |
| 3 | cloud_agent.py | `_send_claim_handoff_summary` tried `.get('whatsapp_number')` on donna_users which lacked the column | Added ALTER TABLE migration + config fallback by email match |
| 4 | web_api.py | Claim endpoint returned before triggering handoff summary | Found and patched correct claim endpoint |

### Commits this session
*(pending — run git commit after this update)*

### Service state
- `cloud_agent.service` — active (running), no errors
- All previous 20 scheduler jobs active

### What is next
- [ ] Per-user Gmail/calendar OAuth self-service flow (user_integrations table exists, needs OAuth dance + "Connect Gmail" button)
- [ ] Support agent email workflow: email summaries in web UI + draft reply with approve/reject
- [ ] Contact name enrichment from ERPNext Customer doctype (nightly sync)
- [ ] Outbound WhatsApp template selection UI (API call to get approved templates, pick & send)

---

## Session: 2026-04-28 (Part 3 — remaining features)

### Summary
Implemented all four remaining features from the audit list.

### What was done

**cloud_agent.py**
- `job_enrich_contacts_from_erp`: nightly (2am KSA) job fetches ERPNext Contact records and enriches local contacts table with full_name, email_id, company_name. Runs via APScheduler cron registered in `post_init`.

**web_api.py**
- `GET /api/whatsapp/templates` — calls `erp.get_whatsapp_templates()` and returns approved Meta templates
- `GET /api/oauth/google/start` — starts Google Device Authorization Flow; returns device_code, user_code, verification_url for the user to open on their phone
- `POST /api/oauth/google/poll` — polls token endpoint until user approves; on success fetches Gmail email address and saves to `user_integrations` table
- `DELETE /api/oauth/google` — disconnects (removes from user_integrations)
- `GET /api/oauth/status` — returns which integrations the current user has connected
- `GET /api/email/inbox` — fetches user's unread Gmail messages using their stored per-user credentials
- `POST /api/email/draft` — asks Donna to draft a reply to a given email (sends prompt to Claude)
- `POST /api/email/send` — sends an approved draft via the user's connected Gmail account

**web/Donna.html**
- `GmailConnectModal`: device flow UI — shows user_code + verification_url, polls until connected
- `EmailInboxPanel`: two-pane panel — left: unread email list; right: Donna's draft reply with Approve & Send button. Includes Connect Gmail prompt if not yet connected.
- `OutboundWAComposer`: when 24h window is closed, now shows real approved template list from `/api/whatsapp/templates`. Click to select, send button becomes "Send template: name"
- 'My Email Inbox' added to Communication nav section

### What was done (ERPNext contact sync)
- Nightly `erp_contact_sync` cron at 2am KSA pulls all Contact records with mobile_no/phone, enriches local contacts table. 21st scheduler job.

### Commits this session
*(pending)*

### Service state
- `cloud_agent.service` — active, 21 scheduler jobs
- All new endpoints active on port 8080

### What is next
- [ ] Per-user Google Calendar integration (OAuth done, but no calendar-specific UI)
- [ ] Template parameter input UI (allow filling in {{1}} {{2}} placeholders before sending)
- [ ] Support agent notification: when new email arrives in their connected inbox (push or WhatsApp)

---

## Session: 2026-04-28 (Part 4 — final remaining items)

### Summary
Implemented the three remaining items: template param inputs, per-user email push, and calendar UI.

### What was done

**erpnext_client.py**
- `get_whatsapp_templates`: now parses BODY component to extract `body_text` and `param_count` (count of {{1}}, {{2}} placeholders). API response includes both fields.

**database.py**
- `list_all_user_integrations(integration)`: returns all users who have a specific integration connected (used for per-user email push).

**cloud_agent.py**
- `job_email_check`: after checking Talha's inbox, now loops through all users with Gmail connected. For each, fetches unread messages, marks as processed, and creates a Donna notification (`add_notification`) for new emails.

**web_api.py**
- `GET /api/calendar/events?days=N` — returns upcoming events from admin Google Calendar (uses existing google_client credentials)
- `POST /api/calendar/events` — creates a calendar event (optional Google Meet link)
- `DELETE /api/calendar/events/{event_id}` — deletes an event

**web/Donna.html**
- `OutboundWAComposer`: when a template with `param_count > 0` is selected, shows per-placeholder input fields ({{1}}, {{2}}…) and a preview of the template body text
- `CalendarPanel`: slide-out panel showing next 14 days of events; event cards with date badge, time, location, attendees, Meet link; "+ New Event" form with datetime pickers, attendees, location, description, and Google Meet toggle; delete button per event
- 'Calendar' added to Communication nav section

### Service state
- Active, 21 scheduler jobs (unchanged)

### What is next
- All planned items complete ✅

---

## Session: 2026-04-28/29 — Bug fixes, message ordering, new features

### Summary
Investigation and fix session. Resolved two critical bugs that prevented Donna from replying to customers. Added three new features (delivery receipts, ticket-from-chat, job applicant type). Fixed message scrambling across all chat windows. Fixed mobile keyboard layout. Fixed cross-device sync. Fixed user identity recognition.

### Bug fixes

**Critical — Donna not replying to customers**
- `database.py`: `is_customer_message_recently_processed` queried `customer_phone` (column does not exist — actual column is `phone_number`). This crashed `job_whatsapp_inbound_poll` on every run since the function was introduced, making the entire 5-min fallback poll dead.
- `cloud_agent.py`: `handle_customer_message` crashed with `AttributeError: 'NoneType'.strip()` when `contact['name']` field is NULL in DB. `.get('name', '')` only returns the default when the key is absent, not when the value is None. Fixed: `((contact or {}).get('name') or '').strip()`.
- Manually triggered Donna to reply to missed customer message (+966504471537) via one-off script.

**Timestamps — all stored as UTC, displayed wrong**
- All conversation SELECT functions in `database.py` now apply `datetime(timestamp, '+3 hours')` so every timestamp the UI receives is already KSA time. Applied to: `get_customer_conversation_history`, `get_team_conversation_history`, `get_admin_conversation`, `get_conversation_thread`, `get_notifications`.

**Message scrambling in all chat windows**
- Root cause 1: Index-based React keys (`hist_N`, `team_api_N`, `cust_N`) — shift when list grows, React re-assigns DOM nodes.
- Root cause 2: Team merge used `text+ts` dedup and appended local messages at the end without sorting.
- Root cause 3: `ts` only stored `HH:MM` — no full timestamp for ordering.
- Root cause 4: `makeInitialThreads` had `id:1` (number) — exploded `.startsWith()` call.
- Fix: Added `stableId(direction, timestamp, content)` (djb2 hash → `db_` prefix), `optId()` (`opt_` prefix for local messages), `sortMsgs()`, `dedupMsgs()`. Every message now has a `sortKey` (full ISO timestamp). All merge points sort after merging. Admin history, team conv poll, customer conv poll, and `addMessage` all use stable IDs and sorted state.
- Secondary fix: `sortKey` format inconsistency — DB produces `'YYYY-MM-DD HH:MM:SS'` (space), optimistic produces `'YYYY-MM-DDTHH:MM:SS.000Z'` (T). Space < T in ASCII so all DB messages sorted before all optimistic messages. Added `normSortKey()` that replaces space with T before comparison.

**Cross-device sync (PWA ↔ Web)**
- Admin/Donna conversation only loaded once on login, never polled. Messages sent on one device invisible on another until logout/login.
- Fix: Added 10-second polling `useEffect` for admin conversation using same `stableId` + `dedupMsgs` + `sortMsgs` logic.

**Donna not recognizing logged-in user**
- Role suffix said "You are assisting [name]" — model read as general context, not "this person is typing to you." Applied to all roles.
- Fix: Changed to "The person logged in and talking to you right now is [name] (role: [role]). You know exactly who they are. Address them by first name." Applied to all 4 roles (admin, manager, support, viewer).

**Mobile keyboard hides send button**
- Textarea `fontSize:14` triggered iOS auto-zoom on focus (iOS zooms any input < 16px), scaling the layout and pushing the send button off-screen.
- Visual Viewport handler ignored `vv.offsetTop` — on iOS the viewport scrolls up when keyboard appears.
- Fix: `fontSize:16` on textarea. Rewrote handler to set `--vv-height` (vv.height) and `--vv-top` (vv.offsetTop). CSS uses `height: var(--vv-height)` and `transform: translateY(var(--vv-top))`. Added `interactive-widget=resizes-content` to viewport meta for Android Chrome.

**Auto-reply after human releases conversation**
- When agent released a claimed conversation, Donna did not check if there was an unanswered customer message.
- Fix: Release endpoint now checks last message direction. If inbound → fires `handle_customer_message` as background task.

### New features

**Delivery receipts in customer chat**
- `customer_conversations` table: added `delivery_status` column (idempotent ALTER TABLE).
- `update_delivery_status()` now also updates `customer_conversations` by `wa_message_name` (which stores the wamid for outbound messages).
- `get_customer_conversation_history` SELECT now includes `delivery_status` and `wa_message_name`.
- UI: outbound customer messages show `✓` (grey, sent), `✓✓` (grey, delivered), `✓✓` (blue, read).

**Convert to ticket from chat**
- `POST /api/tickets/draft-from-message`: Claude Haiku extracts suggested title, description, priority from a customer message.
- `POST /api/tickets/create-from-chat`: creates ERPNext ticket + sends WhatsApp confirmation to customer.
- UI: ticket icon on every inbound customer message. Click → Donna drafts fields → slide-in panel → agent reviews → Create & Notify.

**Job applicant contact type**
- Auto-detected from English + Arabic keywords (apply, CV, cooperative training, وظيفة, تقديم, تدريب تعاوني…).
- When detected: `contact_type` updated to `job_applicant` in contacts table.
- Donna system prompt variant: redirects to `botsolutions.tech/careers`, lightly asks about role interest.
- UI: purple 🎓 Job Applicant badge in left sidebar. Prospect contacts get teal badge too.
- Customer list query changed from `WHERE contact_type='customer'` to `WHERE contact_type NOT IN ('blocked','vendor')` — job applicants and prospects now appear in sidebar.

### OAuth investigation
- Abdul Malik could not connect Gmail — "Cannot load OAuth" error.
- Root cause: Google OAuth client in config is **Web Application** type. Device Authorization Flow requires **Desktop app** type. Google returns `{"error":"invalid_client","error_description":"Invalid client type."}`.
- Resolution: Planned — user needs to create a new Desktop app OAuth credential in Google Cloud Console. Config should use separate `google.device_client_id` / `google.device_client_secret` keys so admin calendar integration is not affected.

### Suggestions log
- Cleaned old entries — kept only April 28 items (IDs 26–29).
- #28 (duplicate messages): marked implemented.
- #29 (mobile keyboard): marked implemented.
- #26 (read incoming WA from team) and #27 (unstructured EOD capture): still open.

### Commits this session
```
8a9066e fix: poll dedup wrong column, NoneType crash, UTC->KSA timestamp display
24b1fd5 feat: Donna auto-replies after human releases a conversation
fb22bbf feat: delivery receipts, ticket-from-chat, job applicant type
d3e6703 fix: eliminate message scrambling with stable IDs, sortKey, and sorted merges
3b64ff4 fix: crash on m.id.startsWith — welcome messages had numeric id:1
06c5f31 fix: cross-device sync, sortKey scramble, identity recognition for all users
e06489d fix: mobile keyboard pushes send button off-screen (#29)
```

### Service state
- `cloud_agent.service` — active (running), no errors
- 21 scheduler jobs active (unchanged)

### What is next
- [ ] #26 — Read incoming WhatsApp messages from team members
- [ ] #27 — Capture unstructured EOD submissions from team
- [ ] Gmail OAuth: create Desktop app credential in Google Cloud Console; update config to use `device_client_id` / `device_client_secret` separate from admin calendar credentials
- [ ] Quotations tool in ERPNext (suggestion #25, removed from log but still valid)
- [ ] Scheduled WhatsApp/email reminders (suggestion #16/17)

---

## Session: 2026-04-29 — Reminders, EOD overhaul, unified conversation flow, coaching

### Summary
Feature-heavy session covering: full reminders system, EOD collection fixes and new UI, unified Take Over flow replacing Intervene+Claim, per-thread coaching panel, role gating for EOD/team, suggestions tool for all users, mobile keyboard fix followup bugs.

### Features built

**Reminders tool (cloud_agent.py, database.py, web_api.py, Donna.html)**
- `reminders` table: id, created_by, target_name, target_whatsapp, target_username, reminder_text, scheduled_at, status, sent_at, notify_setter, calendar_added
- `set_reminder` Claude tool: resolves natural language times from system prompt context, auto-populates target WhatsApp from whitelist by name match, handles "self"/"me"
- `job_check_reminders`: runs every 60 seconds, fires WhatsApp + `add_notification()` + targeted PWA push (per-user, not broadcast) for each due reminder. Notifies setter when firing for someone else.
- `GET /api/reminders`: role-aware — admin with `view_all_reminders` sees all, others see created_by=me OR target_username=me
- `DELETE /api/reminders/{id}`: creator/target/admin only
- RemindersPanel: slide-in with filter tabs (pending/sent/cancelled/all), colour-coded status icons, progress bar, cancel button, attribution for admin view
- Bug fixes: push was broadcasting to all users instead of target only; WhatsApp not sent for self-reminders because Claude didn't look up the number — fixed at both tool handler and job_check_reminders level

**Suggestions tool for all users**
- `submitted_by` column added to suggestions table
- `add_suggestion()` accepts and stores submitted_by
- Tool description rewritten to be user-facing: triggers on "log this", "add a suggestion", "report an issue"
- `_ALWAYS_AVAILABLE` set added: add_suggestion and set_reminder never filtered for any role

**EOD system overhaul**
- Fix 1: Before sending new check-in, detect if existing session has member content — finalise it first before resetting transcript. Prevents data loss when job fires multiple times.
- Fix 2: Auto-finalise when first reply >= 40 words — skips unnecessary follow-up for comprehensive responses (covers Arslan-style detailed updates)
- Fix 3: At 4:55pm force-finalise all open sessions: content → summarise, no content → scan inbound messages for day, nothing → save status=no_response
- Fix 4: job_eod_summary covers all prompted members, not just those with report_text
- DB helpers: `get_open_eod_sessions()`, `get_team_inbound_messages_for_date()`, `get_all_prompted_members_for_date()`
- API guards: `/api/team/conversations/{id}` requires view_team_chat, `/api/reports/daily` and `/api/reports/member/{wa}` require view_eod_summary
- `GET /api/reports/all-members?date=`: returns all team members with EOD status sorted by submission state
- view_eod_summary and view_team_chat seeded: admin + manager only
- TeamSection and ReportsSection gated to admin/manager in sidebar
- EODPanel: split-screen slide-in with date picker, progress bar, member list with colour-coded status (submitted/no_response/pending/not_prompted), report detail pane with proper markdown bullet rendering
- Arslan Hassan April 28 report retroactively generated and saved
- EOD Reports added to Communication tools section (managerOnly)

**Unified Take Over flow**
- Removed `intervening` state entirely — replaced with claim-derived state from `activeCustomer.claimed_by` (DB-backed, polls every 30s)
- `isMine` = claimed_by === my username → unlocks input, shows teal release bar
- `isOthers` = claimed_by !== me → shows who has it, admin gets Override button
- Unclaimed → "Take Over" button (calls /api/customers/{phone}/claim, refreshes customer list)
- Release bar shows name + "Release →" button (calls release API)
- Admin Override available when conversation is claimed by someone else
- ClaimButton component removed — functionality absorbed into bottom bar
- showReadOnly: team/report = always RO; customer = RO unless isMine
- Intervene was local state (lost on refresh, didn't pause Donna, no conflict detection). Take Over is DB-backed — Donna truly pauses, persists across devices.

**CoachingPanel (Ask Donna privately)**
- 🧠 Ask Donna button in conversation header — always visible on customer threads regardless of claim state. Previously hidden inside the locked input section (invisible when Donna handles = always invisible).
- Slide-in floating panel (position:fixed bottom-right, doesn't block conversation)
- Last 5 inbound customer messages injected as context into API call
- Per-thread state: `coachingState` dict keyed by threadId — switching customers preserves context
- 5 quick-prompt chips: one-tap questions without typing
- Custom question input with Enter-to-submit

### Bug fixes

| Commit | Fix |
|---|---|
| 8a9066e | Poll dedup wrong column (customer_phone vs phone_number) + NoneType crash + UTC→KSA timestamps |
| 24b1fd5 | Auto-reply when human releases conversation |
| fb22bbf | Delivery receipts, ticket-from-chat, job applicant type |
| d3e6703 | Message scrambling — stable IDs, sortKey, sorted merges |
| 3b64ff4 | Crash: welcome messages had numeric id:1, startsWith failed |
| 06c5f31 | Cross-device sync (PWA↔Web), sortKey format mismatch, identity recognition for all users |
| e06489d | Mobile keyboard — font-size 16px, Visual Viewport handler, interactive-widget meta |
| 9f2a52a | Reminder push to wrong users; WhatsApp missing for self-reminders |
| 78a85d7 | Blank screen from literal newlines inside JS template literals (Babel silent failure) |

### Investigated (not implemented)

**Gmail OAuth blocked**: `{"error":"invalid_client","error_description":"Invalid client type."}` — Google OAuth client in config is Web Application type. Device Authorization Flow requires Desktop app type. Needs new credential in Google Cloud Console.

### Service state
- `cloud_agent.service` — active, 22 scheduler jobs (added reminder_check every 1min)
- All new endpoints active on port 8080

### Commits this session
```
78a85d7 fix: blank screen from literal newlines inside JS template literals
7a2a70e feat: unified Take Over flow + CoachingPanel with context and quick prompts
3b6b328 feat: EOD system overhaul — role gating, fixed collection, new panel UI
9f2a52a fix: reminder push sent to wrong users, WhatsApp missing for self-reminders
001a992 feat: suggestions tool available to all users with reporter tracking
96f5778 fix: add PWA push notification to reminder delivery
722eadd feat: reminders tool — set, schedule, fire, and manage reminders
```

### What is next
- [ ] Gmail OAuth: create Desktop app credential in Google Cloud Console; use device_client_id/device_client_secret config keys separate from calendar
- [ ] Read incoming WhatsApp from team members (suggestion #26)
- [ ] Capture unstructured EOD submissions — now partially addressed by auto-finalize, but proactive detection still valuable (suggestion #27)
- [ ] Quotations tool in ERPNext (P4)
- [ ] Scheduled WhatsApp/email reminders superseded by Reminders tool — mark P5 done
