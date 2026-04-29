"""
SQLite persistence layer for Cloud Agent.
Stores GL snapshots, ZATCA alert history, and conversation context.
"""
import sqlite3
import json
from datetime import datetime
from config import CONFIG


def _conn():
    conn = sqlite3.connect(CONFIG["db_path"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    with _conn() as conn:
        # Enable WAL mode: better concurrent read/write under multiple processes
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS gl_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                company     TEXT,
                account     TEXT,
                debit       REAL DEFAULT 0,
                credit      REAL DEFAULT 0,
                voucher_type TEXT,
                voucher_no  TEXT,
                party       TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS zatca_alerts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                log_name        TEXT UNIQUE,
                invoice_ref     TEXT,
                status          TEXT,
                zatca_status    TEXT,
                http_code       INTEGER,
                alerted_at      TEXT,
                ticket_created  INTEGER DEFAULT 0,
                ticket_name     TEXT
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                channel     TEXT DEFAULT 'telegram',
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS scheduled_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name    TEXT NOT NULL,
                ran_at      TEXT DEFAULT (datetime('now')),
                result      TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_snapshots (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date    TEXT NOT NULL,
                doc_type         TEXT NOT NULL,
                doc_name         TEXT NOT NULL,
                customer         TEXT,
                amount           REAL DEFAULT 0,
                days_outstanding INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS communication_log (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at             TEXT DEFAULT (datetime('now')),
                channel             TEXT NOT NULL,
                recipient_name      TEXT,
                recipient_address   TEXT NOT NULL,
                subject             TEXT,
                message_preview     TEXT,
                status              TEXT DEFAULT 'sent',
                reference_doctype   TEXT,
                reference_name      TEXT,
                error               TEXT
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                created_by       TEXT NOT NULL,
                target_name      TEXT NOT NULL,
                target_whatsapp  TEXT,
                target_username  TEXT,
                reminder_text    TEXT NOT NULL,
                scheduled_at     TEXT NOT NULL,
                status           TEXT DEFAULT 'pending',
                sent_at          TEXT,
                notify_setter    INTEGER DEFAULT 0,
                calendar_added   INTEGER DEFAULT 0,
                created_at       TEXT DEFAULT (datetime('now', '+3 hours'))
            );
            CREATE INDEX IF NOT EXISTS idx_rem_status ON reminders(status, scheduled_at);
            CREATE INDEX IF NOT EXISTS idx_rem_user ON reminders(created_by, target_username);

            CREATE TABLE IF NOT EXISTS suggestions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                description      TEXT NOT NULL,
                reason           TEXT,
                priority         TEXT DEFAULT 'Medium',
                date_noticed     TEXT DEFAULT (date('now')),
                status           TEXT DEFAULT 'open',
                implemented_date TEXT
            );

            CREATE TABLE IF NOT EXISTS collections_tracker (
                invoice_name     TEXT PRIMARY KEY,
                customer         TEXT,
                amount           REAL DEFAULT 0,
                due_date         TEXT,
                first_seen       TEXT,
                last_seen        TEXT,
                days_overdue     INTEGER DEFAULT 0,
                times_flagged    INTEGER DEFAULT 0,
                resolved         INTEGER DEFAULT 0,
                resolved_date    TEXT
            );

            CREATE TABLE IF NOT EXISTS chart_of_accounts (
                name             TEXT PRIMARY KEY,
                account_name     TEXT,
                account_number   TEXT,
                account_type     TEXT,
                root_type        TEXT,
                parent_account   TEXT,
                is_group         INTEGER DEFAULT 0,
                company          TEXT,
                updated_at       TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_coa_company   ON chart_of_accounts(company);
            CREATE INDEX IF NOT EXISTS idx_coa_root_type ON chart_of_accounts(root_type);
            CREATE INDEX IF NOT EXISTS idx_coa_acc_type  ON chart_of_accounts(account_type);

            CREATE TABLE IF NOT EXISTS team_interactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                member_name     TEXT NOT NULL,
                member_whatsapp TEXT NOT NULL,
                direction       TEXT NOT NULL,
                message         TEXT NOT NULL,
                ticket_ref      TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ti_member ON team_interactions(member_whatsapp);
            CREATE INDEX IF NOT EXISTS idx_ti_created ON team_interactions(created_at);

            CREATE TABLE IF NOT EXISTS ticket_assignments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_name         TEXT NOT NULL,
                ticket_subject      TEXT,
                assigned_to_name    TEXT NOT NULL,
                assigned_to_whatsapp TEXT NOT NULL,
                assigned_at         TEXT DEFAULT (datetime('now')),
                reminded_at         TEXT,
                reminder_count      INTEGER DEFAULT 0,
                acknowledged        INTEGER DEFAULT 0,
                acknowledged_at     TEXT,
                resolved            INTEGER DEFAULT 0,
                resolved_at         TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_ta_assignee ON ticket_assignments(assigned_to_whatsapp);
            CREATE INDEX IF NOT EXISTS idx_ta_ticket   ON ticket_assignments(ticket_name);

            CREATE TABLE IF NOT EXISTS team_pending_state (
                whatsapp    TEXT PRIMARY KEY,
                action      TEXT NOT NULL,
                ticket_name TEXT NOT NULL,
                context     TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS team_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_member_name TEXT NOT NULL,
                whatsapp_number TEXT NOT NULL,
                direction TEXT NOT NULL,
                message_content TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now')),
                ticket_reference TEXT,
                processed INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_tc_number ON team_conversations(whatsapp_number);
            CREATE INDEX IF NOT EXISTS idx_tc_ts ON team_conversations(timestamp);

            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                whatsapp_number TEXT NOT NULL,
                member_name TEXT NOT NULL,
                report_date TEXT NOT NULL,
                report_text TEXT NOT NULL,
                status TEXT DEFAULT 'submitted',
                raw_conversation TEXT,
                submitted_at TEXT,
                prompted_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(report_date, whatsapp_number)
            );
            CREATE INDEX IF NOT EXISTS idx_dr_number ON daily_reports(whatsapp_number);
            CREATE INDEX IF NOT EXISTS idx_dr_date ON daily_reports(report_date);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_dr_date_wa ON daily_reports(report_date, whatsapp_number);

            CREATE TABLE IF NOT EXISTS eod_session_state (
                whatsapp_number TEXT PRIMARY KEY,
                state TEXT NOT NULL DEFAULT 'idle',
                transcript TEXT NOT NULL DEFAULT '',
                started_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                user_name TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                last_used TEXT,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS admin_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                direction TEXT NOT NULL,
                message_content TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now')),
                thread TEXT DEFAULT 'admin'
            );
            CREATE INDEX IF NOT EXISTS idx_ac_user ON admin_conversations(username, timestamp);

            CREATE TABLE IF NOT EXISTS donna_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                category TEXT DEFAULT 'info',
                timestamp TEXT DEFAULT (datetime('now')),
                read INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS pending_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_member_number TEXT NOT NULL,
                ticket_id TEXT NOT NULL,
                message_sent TEXT NOT NULL,
                sent_at TEXT DEFAULT (datetime('now')),
                context_resolved INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_pc_number ON pending_context(team_member_number);


            CREATE TABLE IF NOT EXISTS whatsapp_conversations (
                contact_number TEXT PRIMARY KEY,
                last_inbound_message_time TEXT,
                last_outbound_message_time TEXT,
                window_active INTEGER DEFAULT 0,
                last_checked TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS email_memory (
                contact_email TEXT PRIMARY KEY,
                contact_name TEXT,
                company TEXT,
                last_action_taken TEXT,
                last_action_date TEXT,
                preferred_response_type TEXT,
                notes TEXT,
                history TEXT DEFAULT '[]'
            );
            CREATE INDEX IF NOT EXISTS idx_em_email ON email_memory(contact_email);

            CREATE TABLE IF NOT EXISTS processed_emails (
                message_id TEXT PRIMARY KEY,
                thread_id TEXT,
                processed_at TEXT DEFAULT (datetime('now')),
                action_taken TEXT
            );

            CREATE TABLE IF NOT EXISTS client_profiles (
                customer_name TEXT PRIMARY KEY,
                primary_contact TEXT,
                primary_email TEXT,
                primary_whatsapp TEXT,
                erp_customer_id TEXT,
                payment_behavior TEXT,
                avg_days_to_pay REAL,
                open_invoices_count INTEGER DEFAULT 0,
                open_invoices_value REAL DEFAULT 0,
                open_tickets_count INTEGER DEFAULT 0,
                last_interaction_date TEXT,
                last_interaction_type TEXT,
                relationship_health TEXT DEFAULT 'Green',
                notes TEXT,
                last_updated TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sla_alerts_sent (
                ticket_id   TEXT NOT NULL,
                alert_sent_at TEXT NOT NULL,
                alert_type  TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sla_alerts_ticket ON sla_alerts_sent(ticket_id);

            CREATE TABLE IF NOT EXISTS sla_rules (
                priority TEXT PRIMARY KEY,
                response_sla_hours REAL NOT NULL,
                resolution_sla_hours REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS team_members_db (
                whatsapp_number TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT,
                email TEXT,
                max_tickets INTEGER DEFAULT 10,
                current_open_tickets INTEGER DEFAULT 0,
                last_interaction_summary TEXT,
                last_updated TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS wa_poll_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS contacts (
                phone_number TEXT PRIMARY KEY,
                contact_type TEXT DEFAULT 'customer',
                name TEXT,
                company TEXT,
                language TEXT DEFAULT 'en',
                assigned_team_member TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP,
                total_messages INTEGER DEFAULT 0,
                notes TEXT,
                flagged INTEGER DEFAULT 0,
                flag_reason TEXT,
                pending_action TEXT,
                pending_action_data TEXT
            );

            CREATE TABLE IF NOT EXISTS customer_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                direction TEXT NOT NULL,
                message_content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                wa_message_name TEXT,
                ticket_reference TEXT,
                handled_by TEXT DEFAULT 'donna',
                language TEXT DEFAULT 'en'
            );
            CREATE INDEX IF NOT EXISTS idx_cc_phone ON customer_conversations(phone_number);
            CREATE INDEX IF NOT EXISTS idx_cc_ts ON customer_conversations(timestamp);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_wa_name ON customer_conversations(wa_message_name)
                WHERE wa_message_name IS NOT NULL;

            CREATE TABLE IF NOT EXISTS customer_escalations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                customer_name TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_to TEXT,
                status TEXT DEFAULT 'pending',
                ticket_created TEXT,
                resolved_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_ce_phone ON customer_escalations(phone_number);
            CREATE INDEX IF NOT EXISTS idx_ce_status ON customer_escalations(status);
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'team',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            );
        """)


def save_gl_entries(entries, snapshot_date=None):
    """Bulk-insert GL entries for a snapshot."""
    if not entries:
        return 0
    snap_date = snapshot_date or date.today().isoformat()
    rows = [
        (snap_date, e.get("company"), e.get("account"), e.get("debit", 0),
         e.get("credit", 0), e.get("voucher_type"), e.get("voucher_no"), e.get("party"))
        for e in entries
    ]
    with _conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO gl_snapshots "
            "(snapshot_date,company,account,debit,credit,voucher_type,voucher_no,party) "
            "VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
    return len(rows)


def get_known_zatca_log_names():
    """Return set of ZATCA log names we've already alerted on."""
    with _conn() as conn:
        rows = conn.execute("SELECT log_name FROM zatca_alerts").fetchall()
    return {r["log_name"] for r in rows}


def record_zatca_alert(log_name, invoice_ref, status, zatca_status, http_code,
                       ticket_created=False, ticket_name=None):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO zatca_alerts "
            "(log_name,invoice_ref,status,zatca_status,http_code,alerted_at,ticket_created,ticket_name) "
            "VALUES (?,?,?,?,?,datetime('now'),?,?)",
            (log_name, invoice_ref, status, zatca_status, http_code,
             int(ticket_created), ticket_name),
        )


def add_message(role, content, channel="telegram"):
    """Append a message to conversation history."""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO conversation_history (role,content,channel) VALUES (?,?,?)",
            (role, content, channel),
        )


def get_recent_messages(limit=20, channel="telegram"):
    """Return the last N messages for Claude context, scoped to a channel."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversation_history WHERE channel=? ORDER BY id DESC LIMIT ?",
            (channel, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def log_scheduled_run(job_name, result):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO scheduled_runs (job_name,result) VALUES (?,?)",
            (job_name, str(result)[:500]),
        )


def upsert_collections(overdue_invoices):
    """Upsert current overdue invoices into the tracker; mark missing ones resolved."""
    from datetime import date as _date
    today = _date.today().isoformat()
    current_names = set()

    with _conn() as conn:
        for x in overdue_invoices:
            name = x.get("name", "")
            if not name:
                continue
            current_names.add(name)
            try:
                days_overdue = (_date.today() - _date.fromisoformat(x.get("due_date", today))).days
            except Exception:
                days_overdue = 0
            existing = conn.execute(
                "SELECT invoice_name, times_flagged FROM collections_tracker WHERE invoice_name = ?",
                (name,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE collections_tracker SET last_seen=?, days_overdue=?, times_flagged=times_flagged+1, "
                    "amount=?, resolved=0, resolved_date=NULL WHERE invoice_name=?",
                    (today, days_overdue, x.get("outstanding_amount", 0), name),
                )
            else:
                conn.execute(
                    "INSERT INTO collections_tracker (invoice_name,customer,amount,due_date,first_seen,last_seen,days_overdue,times_flagged) "
                    "VALUES (?,?,?,?,?,?,?,1)",
                    (name, x.get("customer", ""), x.get("outstanding_amount", 0),
                     x.get("due_date", ""), today, today, days_overdue),
                )

        # Mark resolved: active invoices no longer in overdue list
        active = conn.execute(
            "SELECT invoice_name FROM collections_tracker WHERE resolved=0"
        ).fetchall()
        for row in active:
            if row["invoice_name"] not in current_names:
                conn.execute(
                    "UPDATE collections_tracker SET resolved=1, resolved_date=? WHERE invoice_name=?",
                    (today, row["invoice_name"]),
                )


def get_active_escalations():
    """Return active (unresolved) tracked invoices, sorted by times_flagged desc."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT invoice_name, customer, amount, due_date, first_seen, days_overdue, times_flagged "
            "FROM collections_tracker WHERE resolved=0 ORDER BY times_flagged DESC",
        ).fetchall()
    return [dict(r) for r in rows]


def add_suggestion(description, reason="", priority="Medium"):
    """Add a suggestion if no open one with the same description prefix already exists."""
    prefix = description[:80]
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM suggestions WHERE status='open' AND description LIKE ?",
            (prefix + "%",),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO suggestions (description, reason, priority) VALUES (?,?,?)",
                (description, reason, priority),
            )


def get_suggestions(status="open"):
    """Return suggestions filtered by status."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, description, reason, priority, date_noticed, status "
            "FROM suggestions WHERE status=? ORDER BY "
            "CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, date_noticed DESC",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_suggestion(suggestion_id, status, implemented_date=None):
    """Dismiss or mark a suggestion as implemented."""
    with _conn() as conn:
        conn.execute(
            "UPDATE suggestions SET status=?, implemented_date=? WHERE id=?",
            (status, implemented_date, suggestion_id),
        )


def get_job_empty_streak(job_name, threshold=7):
    """Return True if the last `threshold` runs of a job all had 0 in the result."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT result FROM scheduled_runs WHERE job_name=? ORDER BY id DESC LIMIT ?",
            (job_name, threshold),
        ).fetchall()
    if len(rows) < threshold:
        return False
    return all("0" in (r["result"] or "") for r in rows)


def save_daily_snapshot(snapshot_date, overdue, proformas):
    """Save today's overdue invoices and proformas for next-day comparison."""
    from datetime import date as _date
    today = snapshot_date or _date.today().isoformat()
    rows = []
    for x in overdue:
        due = x.get("due_date", today)
        try:
            days_out = (_date.today() - _date.fromisoformat(due)).days
        except Exception:
            days_out = 0
        rows.append((today, "overdue", x.get("name", ""), x.get("customer", ""),
                     x.get("outstanding_amount", 0), days_out))
    for x in proformas:
        txn = x.get("transaction_date", today)
        try:
            days_out = (_date.today() - _date.fromisoformat(txn)).days
        except Exception:
            days_out = 0
        rows.append((today, "proforma", x.get("name", ""), x.get("customer", ""),
                     x.get("grand_total", 0), days_out))
    with _conn() as conn:
        conn.execute("DELETE FROM daily_snapshots WHERE snapshot_date = ?", (today,))
        conn.executemany(
            "INSERT INTO daily_snapshots (snapshot_date,doc_type,doc_name,customer,amount,days_outstanding) "
            "VALUES (?,?,?,?,?,?)",
            rows,
        )


def get_gl_trends(months_back=6):
    """Aggregate GL snapshots by month and voucher_type for trend analysis."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m', snapshot_date) AS month,
                voucher_type,
                SUM(debit)   AS total_debit,
                SUM(credit)  AS total_credit,
                COUNT(*)     AS entry_count
            FROM gl_snapshots
            WHERE snapshot_date >= date('now', ? || ' months')
            GROUP BY month, voucher_type
            ORDER BY month DESC, total_debit DESC
        """, (f"-{months_back}",)).fetchall()
    return [dict(r) for r in rows]


def get_gl_monthly_totals(months_back=6):
    """Aggregate GL snapshots by month only — total debits/credits per month."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m', snapshot_date) AS month,
                SUM(debit)   AS total_debit,
                SUM(credit)  AS total_credit,
                COUNT(*)     AS entry_count
            FROM gl_snapshots
            WHERE snapshot_date >= date('now', ? || ' months')
            GROUP BY month
            ORDER BY month ASC
        """, (f"-{months_back}",)).fetchall()
    return [dict(r) for r in rows]


def save_chart_of_accounts(accounts):
    """Upsert Chart of Accounts entries from ERPNext."""
    if not accounts:
        return 0
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO chart_of_accounts "
            "(name, account_name, account_number, account_type, root_type, "
            "parent_account, is_group, company, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            [
                (
                    a.get("name"), a.get("account_name"), a.get("account_number"),
                    a.get("account_type"), a.get("root_type"), a.get("parent_account"),
                    1 if a.get("is_group") else 0, a.get("company"),
                )
                for a in accounts
            ],
        )
    return len(accounts)


def get_chart_of_accounts(company=None, root_type=None, is_group=None, account_type=None):
    """Query the local Chart of Accounts cache with optional filters."""
    conditions = []
    params = []
    if company:
        conditions.append("company = ?")
        params.append(company)
    if root_type:
        conditions.append("root_type = ?")
        params.append(root_type)
    if is_group is not None:
        conditions.append("is_group = ?")
        params.append(1 if is_group else 0)
    if account_type:
        conditions.append("account_type = ?")
        params.append(account_type)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT name, account_name, account_number, account_type, root_type, "
            f"parent_account, is_group, company "
            f"FROM chart_of_accounts{where} "
            f"ORDER BY root_type, CAST(account_number AS INTEGER), name",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def search_accounts(query, company=None):
    """Search Chart of Accounts by name or account number (partial match)."""
    q = "%" + query + "%"
    params = [q, q, q]
    company_clause = ""
    if company:
        company_clause = " AND company = ?"
        params.append(company)
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT name, account_name, account_number, account_type, root_type, "
            f"parent_account, is_group, company "
            f"FROM chart_of_accounts "
            f"WHERE (account_name LIKE ? OR account_number LIKE ? OR name LIKE ?){company_clause} "
            f"ORDER BY is_group ASC, CAST(account_number AS INTEGER), name "
            f"LIMIT 20",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def coa_loaded():
    """Return True if the chart_of_accounts table has any entries."""
    with _conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM chart_of_accounts").fetchone()[0]
    return count > 0


def log_communication(channel, recipient_name, recipient_address, subject="",
                      message_preview="", status="sent", reference_doctype="",
                      reference_name="", error=""):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO communication_log "
            "(channel,recipient_name,recipient_address,subject,message_preview,status,reference_doctype,reference_name,error) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (channel, recipient_name, recipient_address, subject,
             message_preview[:200], status, reference_doctype, reference_name, error[:500]),
        )


def get_communication_log(limit=20):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT sent_at, channel, recipient_name, recipient_address, subject, status "
            "FROM communication_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_daily_snapshot(snapshot_date):
    """Return overdue and proforma lists from a previous snapshot date."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT doc_type, doc_name, customer, amount, days_outstanding "
            "FROM daily_snapshots WHERE snapshot_date = ?",
            (snapshot_date,),
        ).fetchall()
    overdue = [dict(r) for r in rows if r["doc_type"] == "overdue"]
    proformas = [dict(r) for r in rows if r["doc_type"] == "proforma"]
    return overdue, proformas


# ── Team interaction tracking ─────────────────────────────────────────────────

def log_team_interaction(member_name, member_whatsapp, direction, message, ticket_ref=None):
    """Log an inbound or outbound message with a team member."""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO team_interactions (member_name,member_whatsapp,direction,message,ticket_ref) "
            "VALUES (?,?,?,?,?)",
            (member_name, member_whatsapp, direction, message[:1000], ticket_ref),
        )


def get_team_interactions(since_days=7, member_whatsapp=None):
    """Return team interactions for the last N days, optionally filtered by member."""
    conditions = ["created_at >= date('now', ? || ' days')"]
    params = [f"-{since_days}"]
    if member_whatsapp:
        conditions.append("member_whatsapp = ?")
        params.append(member_whatsapp)
    where = " WHERE " + " AND ".join(conditions)
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT member_name, member_whatsapp, direction, message, ticket_ref, created_at "
            f"FROM team_interactions{where} ORDER BY created_at DESC",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def save_ticket_assignment(ticket_name, ticket_subject, member_name, member_whatsapp):
    """Record that Donna assigned a ticket to a team member via WhatsApp."""
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ticket_assignments "
            "(ticket_name,ticket_subject,assigned_to_name,assigned_to_whatsapp) "
            "VALUES (?,?,?,?)",
            (ticket_name, ticket_subject, member_name, member_whatsapp),
        )


def get_unacknowledged_assignments(member_whatsapp=None):
    """Return assignments that haven't been acknowledged yet."""
    conditions = ["acknowledged = 0", "resolved = 0"]
    params = []
    if member_whatsapp:
        conditions.append("assigned_to_whatsapp = ?")
        params.append(member_whatsapp)
    where = " WHERE " + " AND ".join(conditions)
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT ticket_name, ticket_subject, assigned_to_name, assigned_to_whatsapp, "
            f"assigned_at, reminder_count "
            f"FROM ticket_assignments{where} ORDER BY assigned_at ASC",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def acknowledge_assignment(ticket_name, member_whatsapp):
    """Mark a ticket assignment as acknowledged by the team member."""
    with _conn() as conn:
        conn.execute(
            "UPDATE ticket_assignments SET acknowledged=1, acknowledged_at=datetime('now') "
            "WHERE ticket_name=? AND assigned_to_whatsapp=?",
            (ticket_name, member_whatsapp),
        )


def resolve_assignment(ticket_name):
    """Mark a ticket assignment as resolved."""
    with _conn() as conn:
        conn.execute(
            "UPDATE ticket_assignments SET resolved=1, resolved_at=datetime('now') "
            "WHERE ticket_name=?",
            (ticket_name,),
        )


def bump_reminder_count(ticket_name, member_whatsapp):
    """Increment reminder count and update reminded_at timestamp."""
    with _conn() as conn:
        conn.execute(
            "UPDATE ticket_assignments SET reminder_count=reminder_count+1, reminded_at=datetime('now') "
            "WHERE ticket_name=? AND assigned_to_whatsapp=?",
            (ticket_name, member_whatsapp),
        )


def set_pending_state(whatsapp, action, ticket_name, context=""):
    """
    Record that Donna is waiting for a follow-up from this team member.
    action: 'resolution_report' | 'update_request'
    """
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO team_pending_state (whatsapp, action, ticket_name, context) "
            "VALUES (?, ?, ?, ?)",
            (whatsapp, action, ticket_name, context),
        )


def get_pending_state(whatsapp):
    """Return the pending state for this team member, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT action, ticket_name, context FROM team_pending_state WHERE whatsapp = ?",
            (whatsapp,),
        ).fetchone()
    return dict(row) if row else None


def clear_pending_state(whatsapp):
    """Clear pending state for this team member."""
    with _conn() as conn:
        conn.execute("DELETE FROM team_pending_state WHERE whatsapp = ?", (whatsapp,))


def get_team_activity_summary(since_days=7):
    """Return per-member interaction count and acknowledgement stats."""
    with _conn() as conn:
        inbound = conn.execute(
            "SELECT member_name, member_whatsapp, COUNT(*) as msg_count "
            "FROM team_interactions "
            "WHERE direction='inbound' AND created_at >= date('now', ? || ' days') "
            "GROUP BY member_whatsapp",
            (f"-{since_days}",),
        ).fetchall()

        assignments = conn.execute(
            "SELECT assigned_to_name, assigned_to_whatsapp, "
            "COUNT(*) as total, "
            "SUM(acknowledged) as acked, "
            "SUM(resolved) as resolved, "
            "SUM(reminder_count) as reminders "
            "FROM ticket_assignments "
            "WHERE assigned_at >= date('now', ? || ' days') "
            "GROUP BY assigned_to_whatsapp",
            (f"-{since_days}",),
        ).fetchall()

    msg_map = {r["member_whatsapp"]: {"name": r["member_name"], "messages": r["msg_count"]}
               for r in inbound}
    assign_map = {r["assigned_to_whatsapp"]: dict(r) for r in assignments}

    all_numbers = set(msg_map.keys()) | set(assign_map.keys())
    results = []
    for num in all_numbers:
        m = msg_map.get(num, {})
        a = assign_map.get(num, {})
        results.append({
            "name": m.get("name") or a.get("assigned_to_name", num),
            "whatsapp": num,
            "messages_sent": m.get("messages", 0),
            "tickets_assigned": a.get("total", 0),
            "tickets_acknowledged": a.get("acked", 0),
            "tickets_resolved": a.get("resolved", 0),
            "reminders_needed": a.get("reminders", 0),
        })
    return sorted(results, key=lambda x: -(x["tickets_assigned"] + x["messages_sent"]))

def get_last_inbound_time(whatsapp: str):
    """Return datetime of last inbound message from this WhatsApp number, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT created_at FROM team_interactions "
            "WHERE member_whatsapp=? AND direction='inbound' "
            "ORDER BY created_at DESC LIMIT 1",
            (whatsapp,),
        ).fetchone()
    if row:
        from datetime import datetime
        try:
            return datetime.fromisoformat(row["created_at"])
        except Exception:
            return None
    return None


def whatsapp_window_open(whatsapp: str) -> bool:
    """Return True if this number messaged us within the last 24 hours (Meta window open)."""
    from datetime import datetime, timedelta, timezone
    last = get_last_inbound_time(whatsapp)
    if last is None:
        return False
    # DB stores UTC naive datetimes
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    return (now_utc - last) < timedelta(hours=24)


# ── New helper functions (Phase 5 / Chief of Staff) ───────────────────────────

def _migrate_db():
    """Run safe migrations for columns added after initial schema creation."""
    with _conn() as conn:
        # Add sla_alerts_sent table if missing
        conn.execute('''CREATE TABLE IF NOT EXISTS sla_alerts_sent (
            ticket_id TEXT NOT NULL,
            alert_sent_at TEXT NOT NULL,
            alert_type TEXT
        )''')
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sla_alerts_ticket ON sla_alerts_sent(ticket_id)")
        # Add wa_message_name to team_conversations if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(team_conversations)").fetchall()]
        if 'wa_message_name' not in cols:
            conn.execute("ALTER TABLE team_conversations ADD COLUMN wa_message_name TEXT")
            print("DB migration: added wa_message_name to team_conversations")
        # Create unique index if missing
        indexes = [r[1] for r in conn.execute("PRAGMA index_list(team_conversations)").fetchall()]
        if 'idx_tc_wa_name' not in indexes:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tc_wa_name ON team_conversations(wa_message_name) WHERE wa_message_name IS NOT NULL")
        # Create pending_context if missing
        conn.execute('''CREATE TABLE IF NOT EXISTS pending_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_member_number TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            message_sent TEXT NOT NULL,
            sent_at TEXT DEFAULT (datetime('now')),
            context_resolved INTEGER DEFAULT 0
        )''')
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pc_number ON pending_context(team_member_number)")
        # Add delivery tracking and threading columns if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(team_conversations)").fetchall()]
        if 'sent_wa_message_name' not in cols:
            conn.execute("ALTER TABLE team_conversations ADD COLUMN sent_wa_message_name TEXT")
        if 'delivery_status' not in cols:
            conn.execute("ALTER TABLE team_conversations ADD COLUMN delivery_status TEXT")
        # customer_conversations delivery_status
        cc_cols = [r[1] for r in conn.execute("PRAGMA table_info(customer_conversations)").fetchall()]
        if 'delivery_status' not in cc_cols:
            conn.execute("ALTER TABLE customer_conversations ADD COLUMN delivery_status TEXT")
        if 'conversation_thread_id' not in cols:
            conn.execute("ALTER TABLE team_conversations ADD COLUMN conversation_thread_id TEXT")
        # WhatsApp templates awareness table
        conn.execute("""CREATE TABLE IF NOT EXISTS whatsapp_templates (
            template_name TEXT PRIMARY KEY,
            doc_name TEXT NOT NULL,
            language_code TEXT DEFAULT 'en',
            use_case TEXT,
            has_buttons INTEGER DEFAULT 0,
            variables_count INTEGER DEFAULT 0,
            last_synced TEXT DEFAULT (datetime('now'))
        )""")
        known_templates = [
            ('chat_start', 'chat_start-en', 'en', 'session_opener', 1, 0),
            ('chat_initiation', 'chat_initiation-en', 'en', 'session_opener_alt', 1, 0),
            ('hd_ticket_resolved', 'hd_ticket_resolved-', 'en', 'ticket_resolved_customer', 0, 0),
            ('general_document_assignment', 'general_document_assignment-', 'en', 'ticket_assignment_team', 0, 2),
            ('new_ticket_to_customer', 'new_ticket_to_customer-', 'en', 'new_ticket_customer', 0, 1),
            ('new_profile', 'new_profile-en', 'en', 'new_contact_welcome', 0, 1),
            ('client_welcome', 'client_welcome-', 'en', 'client_onboarding', 0, 1),
            ('new_lead_recorded', 'new_lead_recorded-', 'en', 'crm_lead_created', 0, 1),
            ('incoming_lead', 'incoming_lead-', 'en', 'crm_lead_incoming', 0, 1),
            ('crm_lead_assign_to', 'crm_lead_assign_to-', 'en', 'crm_lead_assigned', 0, 1),
            ('crm_task_notification', 'crm_task_notification-', 'en', 'crm_task_alert', 0, 1),
            ('payment_entry_approval', 'payment_entry_approval-en', 'en', 'payment_approval', 0, 1),
            ('pi_approval_request', 'pi_approval_request-en', 'en', 'invoice_approval', 0, 1),
            ('purchase_invoice_approval_request', 'purchase_invoice_approval_request-en', 'en', 'purchase_approval', 0, 1),
            ('purchase_order_approval_request', 'purchase_order_approval_request-en', 'en', 'po_approval', 0, 1),
            ('overtime_new_template', 'overtime_new_template-en', 'en', 'hr_overtime', 0, 1),
            ('employee_increment_request', 'employee_increment_request-en', 'en', 'hr_increment', 0, 1),
            ('auto_meeting_schedule_link', 'auto_meeting_schedule_link-', 'en', 'meeting_invite', 0, 0),
            ('hello_world', 'hello_world-en_US', 'en', 'test', 0, 0),
            ('incoming_lead_with_url', 'incoming_lead_with_url-en_US', 'en', 'crm_lead_url', 0, 2),
        ]
        for row in known_templates:
            conn.execute(
                "INSERT OR IGNORE INTO whatsapp_templates "
                "(template_name, doc_name, language_code, use_case, has_buttons, variables_count) "
                "VALUES (?,?,?,?,?,?)", row
            )
        print("DB migration complete: delivery tracking + threading + templates table")
        # Customer module tables
        conn.execute('''CREATE TABLE IF NOT EXISTS contacts (
            phone_number TEXT PRIMARY KEY, contact_type TEXT DEFAULT 'customer',
            name TEXT, company TEXT, language TEXT DEFAULT 'en',
            assigned_team_member TEXT, first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP, total_messages INTEGER DEFAULT 0,
            notes TEXT, flagged INTEGER DEFAULT 0, flag_reason TEXT,
            pending_action TEXT, pending_action_data TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS customer_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, phone_number TEXT NOT NULL,
            direction TEXT NOT NULL, message_content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, wa_message_name TEXT,
            ticket_reference TEXT, handled_by TEXT DEFAULT 'donna', language TEXT DEFAULT 'en'
        )''')
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_wa_name ON customer_conversations(wa_message_name) WHERE wa_message_name IS NOT NULL")
        except Exception: pass
        conn.execute('''CREATE TABLE IF NOT EXISTS customer_escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, phone_number TEXT NOT NULL,
            customer_name TEXT, reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_to TEXT, status TEXT DEFAULT 'pending',
            ticket_created TEXT, resolved_at TIMESTAMP
        )''')
        # Add flagged/pending_action columns to contacts if missing
        c_cols = [r[1] for r in conn.execute("PRAGMA table_info(contacts)").fetchall()]
        if c_cols and 'flagged' not in c_cols:
            conn.execute("ALTER TABLE contacts ADD COLUMN flagged INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE contacts ADD COLUMN flag_reason TEXT")
        if c_cols and 'pending_action' not in c_cols:
            conn.execute("ALTER TABLE contacts ADD COLUMN pending_action TEXT")
            conn.execute("ALTER TABLE contacts ADD COLUMN pending_action_data TEXT")
        print("DB migration: customer tables ready")





def log_team_conversation(name, number, direction, content, ticket_ref=None,
                          wa_message_name=None, sent_wa_message_name=None,
                          delivery_status=None, thread_id=None):
    """Log every team WhatsApp message to team_conversations.
    wa_message_name: ERPNext doc name of INBOUND message (for dedup).
    sent_wa_message_name: ERPNext doc name of OUTBOUND message (for delivery tracking).
    """
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO team_conversations "
                "(team_member_name, whatsapp_number, direction, message_content, "
                "ticket_reference, wa_message_name, sent_wa_message_name, delivery_status, conversation_thread_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (name, number, direction, content[:2000], ticket_ref,
                 wa_message_name, sent_wa_message_name, delivery_status, thread_id)
            )
        return True
    except Exception as e:
        # UNIQUE constraint on wa_message_name — duplicate inbound message
        if "UNIQUE" in str(e):
            return False
        raise


def get_team_conversation_history(number, limit=10):
    """Get last N messages with a team member from team_conversations."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT direction, message_content, strftime('%Y-%m-%d %H:%M:%S', datetime(timestamp, '+3 hours')) as timestamp, ticket_reference FROM team_conversations WHERE whatsapp_number=? ORDER BY timestamp DESC LIMIT ?",
            (number, limit)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def update_wa_window(number, direction):
    """Update WhatsApp window tracking on send or receive."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    with _conn() as conn:
        if direction == 'inbound':
            conn.execute(
                "INSERT INTO whatsapp_conversations (contact_number, last_inbound_message_time, window_active) VALUES (?,?,1) "
                "ON CONFLICT(contact_number) DO UPDATE SET last_inbound_message_time=?, window_active=1, last_checked=?",
                (number, now, now, now)
            )
        else:
            conn.execute(
                "INSERT INTO whatsapp_conversations (contact_number, last_outbound_message_time) VALUES (?,?) "
                "ON CONFLICT(contact_number) DO UPDATE SET last_outbound_message_time=?, last_checked=?",
                (number, now, now, now)
            )


def get_wa_poll_state(key):
    with _conn() as conn:
        row = conn.execute("SELECT value FROM wa_poll_state WHERE key=?", (key,)).fetchone()
    return row['value'] if row else None


def set_wa_poll_state(key, value):
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO wa_poll_state (key, value) VALUES (?,?)", (key, str(value)))


def get_processed_email(message_id):
    with _conn() as conn:
        row = conn.execute("SELECT message_id FROM processed_emails WHERE message_id=?", (message_id,)).fetchone()
    return row is not None


def mark_email_processed(message_id, thread_id, action_taken):
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_emails (message_id, thread_id, action_taken) VALUES (?,?,?)",
            (message_id, thread_id, action_taken)
        )


def get_email_memory(contact_email):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM email_memory WHERE contact_email=?", (contact_email,)).fetchone()
    return dict(row) if row else None


def upsert_email_memory(contact_email, contact_name=None, company=None, action=None, notes=None):
    import json
    with _conn() as conn:
        existing = conn.execute("SELECT history FROM email_memory WHERE contact_email=?", (contact_email,)).fetchone()
        history = json.loads(existing['history']) if existing and existing['history'] else []
        if action:
            from datetime import datetime
            history.append({"date": datetime.now().isoformat()[:10], "action": action})
            history = history[-20:]
        conn.execute(
            "INSERT INTO email_memory (contact_email, contact_name, company, last_action_taken, last_action_date, notes, history) "
            "VALUES (?,?,?,?,date('now'),?,?) "
            "ON CONFLICT(contact_email) DO UPDATE SET "
            "contact_name=COALESCE(?,contact_name), company=COALESCE(?,company), "
            "last_action_taken=COALESCE(?,last_action_taken), last_action_date=date('now'), "
            "notes=COALESCE(?,notes), history=?",
            (contact_email, contact_name, company, action, notes, json.dumps(history),
             contact_name, company, action, notes, json.dumps(history))
        )


def init_sla_rules():
    """Seed SLA rules if not present."""
    defaults = [
        ('Urgent', 1, 4),
        ('High', 2, 8),
        ('Medium', 4, 24),
        ('Low', 8, 72),
    ]
    with _conn() as conn:
        for priority, resp, res in defaults:
            conn.execute(
                "INSERT OR IGNORE INTO sla_rules (priority, response_sla_hours, resolution_sla_hours) VALUES (?,?,?)",
                (priority, resp, res)
            )


def sync_team_members_db(team_members):
    """Sync team members from config into team_members_db table."""
    with _conn() as conn:
        for m in team_members:
            conn.execute(
                "INSERT INTO team_members_db (whatsapp_number, name, role, email) VALUES (?,?,?,?) "
                "ON CONFLICT(whatsapp_number) DO UPDATE SET name=?, role=?, email=?",
                (m.get('whatsapp', ''), m.get('name', ''), m.get('role', ''), m.get('email', ''),
                 m.get('name', ''), m.get('role', ''), m.get('email', ''))
            )

def is_wa_message_processed(wa_name):
    """Check if a WhatsApp Message document name has already been processed."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM team_conversations WHERE wa_message_name=?", (wa_name,)
        ).fetchone()
    return row is not None


def add_pending_context(number, ticket_id, message_sent):
    """Record that Donna sent a message to this number about a specific ticket."""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO pending_context (team_member_number, ticket_id, message_sent) VALUES (?,?,?)",
            (number, str(ticket_id), message_sent[:500])
        )


def get_pending_context(number):
    """Get unresolved pending context for a team member (most recent)."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, ticket_id, message_sent, sent_at FROM pending_context "
            "WHERE team_member_number=? AND context_resolved=0 ORDER BY sent_at DESC LIMIT 1",
            (number,)
        ).fetchone()
    return dict(row) if row else None


def resolve_pending_context(number, ticket_id=None):
    """Mark pending context as resolved."""
    with _conn() as conn:
        if ticket_id:
            conn.execute(
                "UPDATE pending_context SET context_resolved=1 WHERE team_member_number=? AND ticket_id=?",
                (number, str(ticket_id))
            )
        else:
            conn.execute(
                "UPDATE pending_context SET context_resolved=1 WHERE team_member_number=?",
                (number,)
            )


def get_last_ticket_messaged(number, hours=48):
    """Get the most recent ticket Donna sent a message about to this number in last N hours."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT ticket_id FROM pending_context "
            "WHERE team_member_number=? AND sent_at >= datetime('now', ? || ' hours') "
            "ORDER BY sent_at DESC LIMIT 1",
            (number, str(-hours))
        ).fetchone()
    if row:
        return row['ticket_id']
    # Also check team_conversations for ticket references
    with _conn() as conn:
        row2 = conn.execute(
            "SELECT ticket_reference FROM team_conversations "
            "WHERE whatsapp_number=? AND direction='outbound' AND ticket_reference IS NOT NULL "
            "AND timestamp >= datetime('now', ? || ' hours') "
            "ORDER BY timestamp DESC LIMIT 1",
            (number, str(-hours))
        ).fetchone()
    return row2['ticket_reference'] if row2 else None


def update_delivery_status(sent_wa_message_name: str, status: str):
    """Update delivery status for a sent message by its wamid."""
    if not sent_wa_message_name:
        return
    with _conn() as conn:
        conn.execute(
            "UPDATE team_conversations SET delivery_status=? WHERE sent_wa_message_name=?",
            (status, sent_wa_message_name)
        )
        conn.execute(
            "UPDATE customer_conversations SET delivery_status=? "
            "WHERE wa_message_name=? AND direction='outbound'",
            (status, sent_wa_message_name)
        )

def get_untracked_outbound(hours=24):
    """Get outbound messages with no delivery status, sent in last N hours."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, team_member_name, whatsapp_number, message_content, sent_wa_message_name "
            "FROM team_conversations "
            "WHERE direction='outbound' AND delivery_status IS NULL "
            "AND sent_wa_message_name IS NOT NULL "
            "AND timestamp >= datetime('now', ? || ' hours')",
            (str(-hours),)
        ).fetchall()
    return [dict(r) for r in rows]

def get_or_create_thread_id(number, ticket_id, hours=48):
    """Get existing active thread for number+ticket, or return a new UUID."""
    import uuid as _uuid
    with _conn() as conn:
        row = conn.execute(
            "SELECT conversation_thread_id FROM team_conversations "
            "WHERE whatsapp_number=? AND ticket_reference=? "
            "AND conversation_thread_id IS NOT NULL "
            "AND timestamp >= datetime('now', ? || ' hours') "
            "ORDER BY timestamp DESC LIMIT 1",
            (number, str(ticket_id), str(-hours))
        ).fetchone()
    if row:
        return row['conversation_thread_id']
    return str(_uuid.uuid4())[:8]

def get_conversation_thread(number, ticket_id=None, limit=20):
    """Get conversation messages in thread order (oldest first)."""
    with _conn() as conn:
        if ticket_id:
            rows = conn.execute(
                "SELECT direction, team_member_name, message_content, strftime('%Y-%m-%d %H:%M:%S', datetime(timestamp, '+3 hours')) as timestamp, ticket_reference, conversation_thread_id "
                "FROM team_conversations "
                "WHERE whatsapp_number=? AND (ticket_reference=? OR conversation_thread_id IN ("
                "  SELECT conversation_thread_id FROM team_conversations "
                "  WHERE whatsapp_number=? AND ticket_reference=? AND conversation_thread_id IS NOT NULL"
                ")) ORDER BY timestamp ASC LIMIT ?",
                (number, str(ticket_id), number, str(ticket_id), limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT direction, team_member_name, message_content, timestamp, ticket_reference, conversation_thread_id "
                "FROM team_conversations WHERE whatsapp_number=? "
                "ORDER BY timestamp ASC LIMIT ?",
                (number, limit)
            ).fetchall()
    return [dict(r) for r in rows]

def get_template_for_use_case(use_case):
    """Return (template_name, doc_name) for a given use case, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT template_name, doc_name FROM whatsapp_templates WHERE use_case=? LIMIT 1",
            (use_case,)
        ).fetchone()
    return dict(row) if row else None

# ── Customer module helpers ────────────────────────────────────────────────────

def get_contact_type(phone_number):
    """Returns 'admin', 'team', or 'customer' based on whatsapp_whitelist in config."""
    wa_whitelist = CONFIG.get("communication", {}).get("whatsapp_whitelist", [])
    for w in wa_whitelist:
        if w.get("number") == phone_number:
            return w.get("access", "team")
    return "customer"


def upsert_contact(phone_number, name=None, company=None, language=None,
                   contact_type='customer', total_messages_delta=1):
    """Create or update a contact record. Increments total_messages by delta."""
    from datetime import datetime as _dt
    now = _dt.now().isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO contacts "
            "(phone_number, contact_type, name, company, language, total_messages, last_active) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(phone_number) DO UPDATE SET "
            "name=COALESCE(?,name), company=COALESCE(?,company), "
            "language=COALESCE(?,language), contact_type=COALESCE(?,contact_type), "
            "total_messages=total_messages+?, last_active=?",
            (phone_number, contact_type, name, company, language or 'en',
             total_messages_delta, now,
             name, company, language, contact_type, total_messages_delta, now)
        )


def get_contact(phone_number):
    """Get a contact record with inbound message_count, or None."""
    with _conn() as conn:
        row = conn.execute(
            """SELECT c.*, COALESCE(m.msg_count,0) as message_count
               FROM contacts c
               LEFT JOIN (
                   SELECT phone_number, COUNT(*) as msg_count
                   FROM customer_conversations WHERE direction='inbound'
                   GROUP BY phone_number
               ) m ON m.phone_number=c.phone_number
               WHERE c.phone_number=?""",
            (phone_number,)
        ).fetchone()
    return dict(row) if row else None


def flag_contact(phone_number, reason):
    """Mark a contact as flagged."""
    with _conn() as conn:
        conn.execute(
            "UPDATE contacts SET flagged=1, flag_reason=? WHERE phone_number=?",
            (reason, phone_number)
        )


def set_pending_action(phone_number, action, data=None):
    """Set a pending_action state for a contact (e.g. 'awaiting_email')."""
    import json as _json
    with _conn() as conn:
        conn.execute(
            "UPDATE contacts SET pending_action=?, pending_action_data=? WHERE phone_number=?",
            (action, _json.dumps(data) if data else None, phone_number)
        )


def clear_pending_action(phone_number):
    """Clear the pending_action state for a contact."""
    with _conn() as conn:
        conn.execute(
            "UPDATE contacts SET pending_action=NULL, pending_action_data=NULL WHERE phone_number=?",
            (phone_number,)
        )


def get_pending_action(phone_number):
    """Get (action, data) for a contact's pending state, or (None, None)."""
    import json as _json
    with _conn() as conn:
        row = conn.execute(
            "SELECT pending_action, pending_action_data FROM contacts WHERE phone_number=?",
            (phone_number,)
        ).fetchone()
    if not row or not row[0]:
        return None, None
    data = None
    if row[1]:
        try:
            data = _json.loads(row[1])
        except Exception:
            data = row[1]
    return row[0], data


def log_customer_conversation(phone_number, direction, content, wa_message_name=None,
                               ticket_ref=None, handled_by='donna', language='en'):
    """Log a customer WhatsApp message. Returns False if duplicate (UNIQUE constraint)."""
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO customer_conversations "
                "(phone_number, direction, message_content, wa_message_name, "
                "ticket_reference, handled_by, language) "
                "VALUES (?,?,?,?,?,?,?)",
                (phone_number, direction, content[:2000], wa_message_name,
                 ticket_ref, handled_by, language)
            )
        return True
    except Exception as e:
        if "UNIQUE" in str(e):
            return False
        raise


def get_customer_conversation_history(phone_number, limit=50):
    """Return last N messages for a customer, oldest first."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT direction, message_content, "
            "strftime('%Y-%m-%d %H:%M:%S', datetime(timestamp, '+3 hours')) as timestamp, "
            "ticket_reference, handled_by, language, delivery_status, wa_message_name "
            "FROM customer_conversations WHERE phone_number=? "
            "ORDER BY timestamp ASC LIMIT ?",
            (phone_number, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def is_customer_message_processed(wa_name):
    """Check if a WA message was already processed in customer_conversations."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM customer_conversations WHERE wa_message_name=?", (wa_name,)
        ).fetchone()
    return row is not None


def count_customer_messages_last_hour(phone_number):
    """Count inbound messages from this customer in the last hour (rate limiting)."""
    with _conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM customer_conversations "
            "WHERE phone_number=? AND direction='inbound' "
            "AND timestamp >= datetime('now', '-1 hours')",
            (phone_number,)
        ).fetchone()[0]
    return count


def create_customer_escalation(phone_number, customer_name, reason, assigned_to=None):
    """Create escalation record; flag the contact. Returns escalation id."""
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO customer_escalations (phone_number, customer_name, reason, assigned_to) "
            "VALUES (?,?,?,?)",
            (phone_number, customer_name or phone_number, reason, assigned_to)
        )
        esc_id = cur.lastrowid
        conn.execute(
            "UPDATE contacts SET flagged=1, flag_reason=? WHERE phone_number=?",
            (reason, phone_number)
        )
    return esc_id


def resolve_customer_escalation(escalation_id, status, ticket_created=None):
    """Update escalation status ('auto_resolved', 'taken', etc.)."""
    with _conn() as conn:
        conn.execute(
            "UPDATE customer_escalations "
            "SET status=?, ticket_created=?, resolved_at=datetime('now') "
            "WHERE id=?",
            (status, ticket_created, escalation_id)
        )


def take_customer_escalation(phone_number, agent_name):
    """Mark the active pending escalation for this number as 'taken'."""
    with _conn() as conn:
        conn.execute(
            "UPDATE customer_escalations SET status='taken', assigned_to=? "
            "WHERE phone_number=? AND status='pending'",
            (agent_name, phone_number)
        )


def get_pending_customer_escalations(timeout_minutes=15):
    """Return pending escalations older than timeout_minutes."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, phone_number, customer_name, reason, created_at, assigned_to "
            "FROM customer_escalations "
            "WHERE status='pending' "
            "AND created_at <= datetime('now', ? || ' minutes')",
            (str(-timeout_minutes),)
        ).fetchall()
    return [dict(r) for r in rows]


def get_active_customer_escalation(phone_number):
    """Get the most recent active (pending/taken) escalation for a phone number."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, phone_number, customer_name, reason, status, assigned_to, created_at "
            "FROM customer_escalations "
            "WHERE phone_number=? AND status IN ('pending','taken') "
            "ORDER BY created_at DESC LIMIT 1",
            (phone_number,)
        ).fetchone()
    return dict(row) if row else None


def get_all_customer_escalations():
    """Return all active escalations for the web interface."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, phone_number, customer_name, reason, status, assigned_to, created_at "
            "FROM customer_escalations "
            "WHERE status IN ('pending','taken') "
            "ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_customers_with_last_message():
    """Return all customer contacts with their last message and escalation info."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                c.phone_number,
                c.name,
                c.company,
                c.language,
                c.flagged,
                c.flag_reason,
                c.total_messages,
                c.last_active,
                c.contact_type,
                (SELECT message_content FROM customer_conversations
                 WHERE phone_number=c.phone_number ORDER BY timestamp DESC LIMIT 1) AS last_message,
                (SELECT timestamp FROM customer_conversations
                 WHERE phone_number=c.phone_number ORDER BY timestamp DESC LIMIT 1) AS last_message_time,
                (SELECT status FROM customer_escalations
                 WHERE phone_number=c.phone_number AND status IN ('pending','taken')
                 ORDER BY created_at DESC LIMIT 1) AS escalation_status,
                (SELECT reason FROM customer_escalations
                 WHERE phone_number=c.phone_number AND status IN ('pending','taken')
                 ORDER BY created_at DESC LIMIT 1) AS escalation_reason
            FROM contacts c
            WHERE c.contact_type NOT IN ('blocked','vendor')
            ORDER BY c.last_active DESC
        """).fetchall()
    return [dict(r) for r in rows]




def get_stale_taken_escalations(timeout_hours: int = 2) -> list:
    """Return taken escalations with no human outbound message in the last timeout_hours."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT ce.id, ce.phone_number, ce.customer_name, ce.assigned_to
            FROM customer_escalations ce
            WHERE ce.status = 'taken'
            AND NOT EXISTS (
                SELECT 1 FROM customer_conversations cc
                WHERE cc.phone_number = ce.phone_number
                AND cc.direction = 'outbound'
                AND cc.handled_by = 'human'
                AND cc.timestamp >= datetime('now', '-' || ? || ' hours')
            )
        """, (timeout_hours,)).fetchall()
    return [dict(r) for r in rows]

# ── Session management ────────────────────────────────────────────────────────

def create_session(token: str, username: str, role: str = 'team', ttl_hours: int = 24):
    """Store a new session token with expiry."""
    from datetime import datetime, timedelta
    expires = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat(sep=' ')[:19]
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (token, username, role, expires_at) VALUES (?, ?, ?, ?)",
            (token, username, role, expires),
        )


def get_session(token: str):
    """Return session dict if token exists and not expired, else None."""
    from datetime import datetime
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE token=? AND expires_at > datetime('now')",
            (token,),
        ).fetchone()
    return dict(row) if row else None


def delete_session(token: str):
    """Remove a session (logout)."""
    with _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def cleanup_expired_sessions():
    """Remove sessions older than their expiry."""
    with _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")



# ── User registry (RBAC) ─────────────────────────────────────────────────────

def _ensure_donna_users():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS donna_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                role TEXT DEFAULT 'support',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT
            )
        """)

_ensure_donna_users()
# Upgrade: add whatsapp_number column if missing
try:
    with _conn() as _c:
        _c.execute('ALTER TABLE donna_users ADD COLUMN whatsapp_number TEXT')
except Exception:
    pass  # column already exists


def set_donna_user_whatsapp(username: str, whatsapp_number):
    with _conn() as conn:
        conn.execute('UPDATE donna_users SET whatsapp_number=? WHERE username=?', (whatsapp_number, username))


def upsert_donna_user(username: str, display_name: str = None, role: str = None):
    """Create or update a user record; always updates last_login."""
    from datetime import datetime
    now = datetime.utcnow().isoformat(sep=' ')[:19]
    with _conn() as conn:
        existing = conn.execute(
            "SELECT role, display_name FROM donna_users WHERE username=?", (username,)
        ).fetchone()
        if existing:
            updates, vals = ["last_login=?"], [now]
            if display_name and not existing["display_name"]:
                updates.append("display_name=?"); vals.append(display_name)
            # Only upgrade role, never silently downgrade
            if role and role in ("admin", "manager") and existing["role"] in ("agent", "support", "viewer"):
                updates.append("role=?"); vals.append(role)
            vals.append(username)
            conn.execute(f"UPDATE donna_users SET {','.join(updates)} WHERE username=?", vals)
        else:
            conn.execute(
                "INSERT INTO donna_users (username, display_name, role, last_login) VALUES (?,?,?,?)",
                (username, display_name, role or 'support', now)
            )


def get_donna_user(username: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM donna_users WHERE username=?", (username,)
        ).fetchone()
    return dict(row) if row else None


def list_donna_users() -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM donna_users ORDER BY role, display_name"
        ).fetchall()
    return [dict(r) for r in rows]


def update_donna_user_role(username: str, role: str):
    with _conn() as conn:
        conn.execute("UPDATE donna_users SET role=? WHERE username=?", (role, username))


def update_donna_user_name(username: str, display_name: str):
    with _conn() as conn:
        conn.execute("UPDATE donna_users SET display_name=? WHERE username=?", (display_name, username))


def deactivate_donna_user(username: str):
    with _conn() as conn:
        conn.execute("UPDATE donna_users SET is_active=0 WHERE username=?", (username,))


def activate_donna_user(username: str):
    with _conn() as conn:
        conn.execute("UPDATE donna_users SET is_active=1 WHERE username=?", (username,))

# ── EOD report helpers ────────────────────────────────────────────────────────

def get_eod_session(whatsapp_number: str):
    """Return current EOD session state dict or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM eod_session_state WHERE whatsapp_number=?",
            (whatsapp_number,),
        ).fetchone()
    return dict(row) if row else None


def set_eod_session(whatsapp_number: str, state: str, transcript: str):
    """Upsert EOD session state for a team member."""
    with _conn() as conn:
        conn.execute(
            """INSERT INTO eod_session_state (whatsapp_number, state, transcript, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(whatsapp_number) DO UPDATE SET
                   state=excluded.state,
                   transcript=excluded.transcript,
                   updated_at=excluded.updated_at""",
            (whatsapp_number, state, transcript),
        )


def clear_eod_session(whatsapp_number: str):
    """Remove EOD session (reset to idle)."""
    with _conn() as conn:
        conn.execute(
            "DELETE FROM eod_session_state WHERE whatsapp_number=?",
            (whatsapp_number,),
        )


def save_daily_report(whatsapp_number: str, member_name: str, report_date: str,
                      report_text: str, raw_conversation: str = None, status: str = 'submitted'):
    """Persist a completed EOD report. Uses ON CONFLICT to upsert by (report_date, whatsapp_number)."""
    from datetime import datetime
    now = datetime.utcnow().isoformat(sep=' ')[:19]
    with _conn() as conn:
        conn.execute(
            """INSERT INTO daily_reports
                   (whatsapp_number, member_name, report_date, report_text,
                    raw_conversation, status, submitted_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(report_date, whatsapp_number) DO UPDATE SET
                   report_text=excluded.report_text,
                   raw_conversation=excluded.raw_conversation,
                   status=excluded.status,
                   submitted_at=excluded.submitted_at""",
            (whatsapp_number, member_name, report_date, report_text,
             raw_conversation, status, now, now),
        )


def log_daily_report_prompt(member_name: str, whatsapp_number: str, report_date: str):
    """Record that a prompt was sent to a member — creates/updates row with status='prompted'."""
    from datetime import datetime
    now = datetime.utcnow().isoformat(sep=' ')[:19]
    with _conn() as conn:
        conn.execute(
            """INSERT INTO daily_reports
                   (whatsapp_number, member_name, report_date, report_text,
                    status, prompted_at, created_at)
               VALUES (?, ?, ?, '', 'prompted', ?, ?)
               ON CONFLICT(report_date, whatsapp_number) DO UPDATE SET
                   prompted_at=excluded.prompted_at""",
            (whatsapp_number, member_name, report_date, now, now),
        )


def is_pending_eod_report(whatsapp_number: str, report_date: str) -> bool:
    """Return True if a prompt was sent but report not yet submitted for this date."""
    with _conn() as conn:
        row = conn.execute(
            """SELECT id FROM daily_reports
               WHERE whatsapp_number=? AND report_date=? AND status='prompted'""",
            (whatsapp_number, report_date),
        ).fetchone()
    return row is not None


def get_daily_reports(report_date: str = None, limit: int = 50):
    """Return daily reports, optionally filtered by date. Adds member_whatsapp alias."""
    _SQL = """SELECT id, whatsapp_number, whatsapp_number AS member_whatsapp,
                      member_name, report_date, report_text,
                      COALESCE(status,'submitted') AS status,
                      raw_conversation, submitted_at, prompted_at, created_at
               FROM daily_reports
               WHERE status != 'prompted' OR report_text != ''"""
    with _conn() as conn:
        if report_date:
            rows = conn.execute(
                _SQL + " AND report_date=? ORDER BY created_at DESC LIMIT ?",
                (report_date, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                _SQL + " ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_member_report_history(whatsapp_number: str, limit: int = 10):
    """Return recent EOD reports for a specific team member."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, whatsapp_number, whatsapp_number AS member_whatsapp,
                      member_name, report_date, report_text,
                      COALESCE(status,'submitted') AS status,
                      raw_conversation, submitted_at, prompted_at, created_at
               FROM daily_reports
               WHERE whatsapp_number=? AND (status != 'prompted' OR report_text != '')
               ORDER BY report_date DESC LIMIT ?""",
            (whatsapp_number, limit),
        ).fetchall()
    return [dict(r) for r in rows]

def is_team_message_recently_processed(whatsapp_number, message_content, within_minutes=3):
    """Content+time dedup — catches webhook/poll overlap where wa_message_name keys differ."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM team_conversations "
            "WHERE whatsapp_number=? AND message_content=? AND direction='inbound' "
            "AND timestamp >= datetime('now', ? || ' minutes') LIMIT 1",
            (whatsapp_number, message_content, '-{}'.format(within_minutes))
        ).fetchone()
    return row is not None


def is_customer_message_recently_processed(phone, message_content, within_minutes=3):
    """Content+time dedup for customer messages."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM customer_conversations "
            "WHERE phone_number=? AND message_content=? AND direction='inbound' "
            "AND timestamp >= datetime('now', ? || ' minutes') LIMIT 1",
            (phone, message_content, '-{}'.format(within_minutes))
        ).fetchone()
    return row is not None

# ── Web Push subscription helpers ─────────────────────────────────────────────

def save_push_subscription(endpoint: str, p256dh: str, auth: str, user_name: str = None):
    """Upsert a push subscription endpoint."""
    with _conn() as conn:
        conn.execute(
            """INSERT INTO push_subscriptions (endpoint, p256dh, auth, user_name, last_used)
               VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(endpoint) DO UPDATE SET
                   p256dh=excluded.p256dh,
                   auth=excluded.auth,
                   active=1,
                   last_used=datetime('now')""",
            (endpoint, p256dh, auth, user_name),
        )


def delete_push_subscription(endpoint: str):
    """Remove a push subscription (unsubscribe or 410 Gone)."""
    with _conn() as conn:
        conn.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))


def get_all_push_subscriptions() -> list:
    """Return all active push subscriptions."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT endpoint, p256dh, auth, user_name FROM push_subscriptions WHERE active=1"
        ).fetchall()
    return [dict(r) for r in rows]

# ── Admin conversation (cross-device Donna chat history) ──────────────────────

def log_admin_message(username: str, direction: str, content: str, thread: str = 'admin'):
    """Log a message in the admin Donna chat thread."""
    with _conn() as conn:
        conn.execute("""
            INSERT INTO admin_conversations (username, direction, message_content, thread)
            VALUES (?, ?, ?, ?)
        """, (username, direction, content, thread))


def get_admin_conversation(username: str, limit: int = 50) -> list:
    """Get recent admin chat messages."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT direction, message_content, strftime('%Y-%m-%d %H:%M:%S', datetime(timestamp, '+3 hours')) as timestamp
            FROM admin_conversations
            WHERE username=? AND thread='admin'
            ORDER BY timestamp DESC LIMIT ?
        """, (username, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Donna notifications (web UI notification panel) ───────────────────────────

def add_notification(title: str, body: str, category: str = 'info'):
    """Store a notification for display in the web UI."""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO donna_notifications (title, body, category) VALUES (?,?,?)",
            (title, body, category)
        )


def get_notifications(limit: int = 20, unread_only: bool = False) -> list:
    """Return recent notifications."""
    with _conn() as conn:
        q = ("SELECT id, title, body, category, read, "
             "strftime('%Y-%m-%d %H:%M:%S', datetime(timestamp, '+3 hours')) as timestamp "
             "FROM donna_notifications")
        if unread_only:
            q += " WHERE read=0"
        q += " ORDER BY timestamp DESC LIMIT ?"
        rows = conn.execute(q, (limit,)).fetchall()
    return [dict(r) for r in rows]


def mark_notifications_read():
    """Mark all notifications as read."""
    with _conn() as conn:
        conn.execute("UPDATE donna_notifications SET read=1 WHERE read=0")


def delete_notification(notif_id: int):
    with _conn() as conn:
        conn.execute("DELETE FROM donna_notifications WHERE id=?", (notif_id,))


def clear_all_notifications():
    with _conn() as conn:
        conn.execute("DELETE FROM donna_notifications")


# ── Role permissions ──────────────────────────────────────────────────────────

def get_role_permissions(role: str) -> dict:
    """Return {permission: granted} dict for a role."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT permission, granted FROM role_permissions WHERE role=?", (role,)
        ).fetchall()
    return {r["permission"]: bool(r["granted"]) for r in rows}


def get_all_role_permissions() -> dict:
    """Return {role: {permission: granted}} for all roles."""
    with _conn() as conn:
        rows = conn.execute("SELECT role, permission, granted FROM role_permissions").fetchall()
    result = {}
    for r in rows:
        result.setdefault(r["role"], {})[r["permission"]] = bool(r["granted"])
    return result


def set_role_permission(role: str, permission: str, granted: bool):
    """Set a single permission flag for a role."""
    with _conn() as conn:
        conn.execute("""
            INSERT INTO role_permissions (role, permission, granted)
            VALUES (?, ?, ?)
            ON CONFLICT(role, permission) DO UPDATE SET granted=excluded.granted
        """, (role, permission, 1 if granted else 0))


def has_permission(username: str, permission: str) -> bool:
    """Check if a user (by username) has a specific permission via their role."""
    user = get_donna_user(username)
    if not user:
        return False
    role = user.get("role", "support")
    with _conn() as conn:
        row = conn.execute(
            "SELECT granted FROM role_permissions WHERE role=? AND permission=?",
            (role, permission)
        ).fetchone()
    return bool(row["granted"]) if row else False


# ── User integrations ─────────────────────────────────────────────────────────

def save_user_integration(username: str, integration: str, token_json: str,
                           email_address: str = None, scopes: str = None):
    """Upsert an OAuth integration for a user."""
    with _conn() as conn:
        conn.execute("""
            INSERT INTO user_integrations (username, integration, token_json, email_address, scopes, connected_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(username, integration) DO UPDATE SET
                token_json=excluded.token_json,
                email_address=excluded.email_address,
                scopes=excluded.scopes,
                connected_at=excluded.connected_at
        """, (username, integration, token_json, email_address, scopes))


def get_user_integration(username: str, integration: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_integrations WHERE username=? AND integration=?",
            (username, integration)
        ).fetchone()
    return dict(row) if row else None


def list_user_integrations(username: str) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT integration, email_address, connected_at FROM user_integrations WHERE username=?",
            (username,)
        ).fetchall()
    return [dict(r) for r in rows]


def add_reminder(created_by: str, target_name: str, reminder_text: str,
                    scheduled_at: str, target_whatsapp: str = None,
                    target_username: str = None, notify_setter: int = 0) -> int:
    """Insert a new reminder. Returns the new row id."""
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO reminders
               (created_by, target_name, target_whatsapp, target_username,
                reminder_text, scheduled_at, notify_setter)
               VALUES (?,?,?,?,?,?,?)""",
            (created_by, target_name, target_whatsapp, target_username,
             reminder_text, scheduled_at, notify_setter)
        )
        return cur.lastrowid


def get_pending_reminders() -> list:
    """Return reminders due to fire (scheduled_at <= now KSA, status=pending)."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM reminders
               WHERE status='pending'
               AND scheduled_at <= datetime('now', '+3 hours')
               ORDER BY scheduled_at ASC"""
        ).fetchall()
    return [dict(r) for r in rows]


def mark_reminder_sent(reminder_id: int):
    with _conn() as conn:
        conn.execute(
            """UPDATE reminders SET status='sent',
               sent_at=datetime('now', '+3 hours') WHERE id=?""",
            (reminder_id,)
        )


def cancel_reminder(reminder_id: int, requesting_user: str, is_admin: bool = False) -> bool:
    """Cancel a pending reminder. Only creator/target or admin can cancel."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM reminders WHERE id=? AND status='pending'", (reminder_id,)
        ).fetchone()
        if not row:
            return False
        r = dict(row)
        if not is_admin and r["created_by"] != requesting_user and r.get("target_username") != requesting_user:
            return False
        conn.execute("UPDATE reminders SET status='cancelled' WHERE id=?", (reminder_id,))
    return True


def get_reminders(username: str, view_all: bool = False) -> list:
    """Return reminders visible to this user based on their access level."""
    with _conn() as conn:
        if view_all:
            rows = conn.execute(
                """SELECT * FROM reminders
                   ORDER BY scheduled_at ASC""",
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM reminders
                   WHERE created_by=? OR target_username=?
                   ORDER BY scheduled_at ASC""",
                (username, username)
            ).fetchall()
    return [dict(r) for r in rows]


def list_all_user_integrations(integration: str) -> list:
    """Return all users who have a specific integration connected."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM user_integrations WHERE integration=?", (integration,)
        ).fetchall()
    return [dict(r) for r in rows]


def remove_user_integration(username: str, integration: str):

    with _conn() as conn:
        conn.execute(
            "DELETE FROM user_integrations WHERE username=? AND integration=?",
            (username, integration)
        )


# ── Conversation claims ───────────────────────────────────────────────────────

def claim_conversation(phone_number: str, username: str, display_name: str) -> bool:
    """Claim a conversation. Returns True if successful, False if already claimed by someone else."""
    with _conn() as conn:
        existing = conn.execute(
            "SELECT claimed_by, active FROM conversation_claims WHERE phone_number=?",
            (phone_number,)
        ).fetchone()
        if existing and existing["active"] and existing["claimed_by"] != username:
            return False
        conn.execute("""
            INSERT INTO conversation_claims (phone_number, claimed_by, claimed_by_name, claimed_at, active)
            VALUES (?, ?, ?, datetime('now'), 1)
            ON CONFLICT(phone_number) DO UPDATE SET
                claimed_by=excluded.claimed_by,
                claimed_by_name=excluded.claimed_by_name,
                claimed_at=excluded.claimed_at,
                released_at=NULL,
                active=1
        """, (phone_number, username, display_name))
        # Pause Donna's AI responses for claimed conversations
        conn.execute(
            "UPDATE contacts SET donna_paused=1 WHERE phone_number=?", (phone_number,)
        )
    return True


def release_conversation(phone_number: str, username: str) -> bool:
    """Release a conversation claim. Only the claimer (or admin) can release."""
    with _conn() as conn:
        conn.execute("""
            UPDATE conversation_claims
            SET released_at=datetime('now'), active=0
            WHERE phone_number=? AND claimed_by=?
        """, (phone_number, username))
        conn.execute(
            "UPDATE contacts SET donna_paused=0 WHERE phone_number=?", (phone_number,)
        )
    return True


def get_conversation_claim(phone_number: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversation_claims WHERE phone_number=? AND active=1",
            (phone_number,)
        ).fetchone()
    return dict(row) if row else None


def get_all_claims() -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_claims WHERE active=1 ORDER BY claimed_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Contact enrichment ────────────────────────────────────────────────────────

def update_contact_enrichment(phone_number: str, **kwargs):
    """Update enrichment fields on a contact: name, email, company, need_category."""
    allowed = {"name", "email", "company", "need_category", "enriched_name", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v}
    if not updates:
        return
    updates["enriched_at"] = "datetime('now')"
    set_parts = []
    vals = []
    for k, v in updates.items():
        if k == "enriched_at":
            set_parts.append(f"{k}=datetime('now')")
        else:
            set_parts.append(f"{k}=?")
            vals.append(v)
    vals.append(phone_number)
    with _conn() as conn:
        conn.execute(
            f"UPDATE contacts SET {', '.join(set_parts)} WHERE phone_number=?", vals
        )


def create_donna_user_manual(username: str, display_name: str, role: str = 'support') -> bool:
    """Pre-create a user (before first login). Returns False if already exists."""
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM donna_users WHERE username=?", (username,)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO donna_users (username, display_name, role, is_active) VALUES (?,?,?,1)",
            (username, display_name, role)
        )
    return True
