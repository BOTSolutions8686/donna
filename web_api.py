"""
Donna Web API — FastAPI server exposing dashboard endpoints.
Runs on port 8080 as an asyncio task alongside the Telegram bot.
"""
import sys
import os
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import secrets
import httpx
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, "/opt/cloud_agent")
from config import CONFIG
import database as db
import erpnext_client as erp

_RIYADH_TZ = timezone(timedelta(hours=3))

def _to_saudi(dt):
    """Convert any datetime to Saudi time (UTC+3). Accepts naive or aware datetimes."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except Exception:
            return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_RIYADH_TZ)

def _fmt_saudi(dt, fmt='%Y-%m-%d %H:%M'):
    """Format a datetime in Saudi time."""
    s = _to_saudi(dt)
    if s is None:
        return ''
    return s.strftime(fmt)
_WEB_DIR = "/opt/cloud_agent/web"

app = FastAPI(title="Donna Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Callback injected by cloud_agent.py at startup ────────────────────────────
_ask_claude_fn = None


def set_ask_claude(fn):
    global _ask_claude_fn
    _ask_claude_fn = fn


# ── Auth ──────────────────────────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)

_ADMIN_ROLES = {"admin"}
_TEAM_ROLES = {"admin", "team"}


def _get_admin_users():
    """Return set of usernames who have admin role from config."""
    return set(CONFIG.get("admin_users", ["Administrator", "talha@botsolutions.tech"]))


async def _verify_token(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
):
    if creds is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = db.get_session(creds.credentials)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return session


async def require_auth(session=Depends(_verify_token)):
    return session


async def require_admin(session=Depends(_verify_token)):
    if session.get("role") not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return session


# ── Auth endpoints ────────────────────────────────────────────────────────────
class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
async def login(body: LoginBody):
    erp_url = CONFIG.get("erpnext", {}).get("url", "").rstrip("/")
    if not erp_url:
        raise HTTPException(status_code=503, detail="ERPNext not configured")
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.post(
                f"{erp_url}/api/method/login",
                data={"usr": body.username, "pwd": body.password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        data = resp.json()
        if data.get("message") != "Logged In":
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # Determine role
        admin_users = _get_admin_users()
        role = "admin" if body.username in admin_users else "team"
        token = secrets.token_urlsafe(32)
        db.create_session(token, body.username, role, ttl_hours=24)
        return {"token": token, "username": body.username, "role": role}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/logout")
async def logout(session=Depends(require_auth)):
    # We don't have access to raw token here easily — use header directly
    raise HTTPException(status_code=200, detail="Logged out")


@app.post("/api/auth/logout-token")
async def logout_token(body: dict):
    token = body.get("token", "")
    if token:
        db.delete_session(token)
    return {"status": "ok"}


@app.get("/api/auth/me")
async def auth_me(session=Depends(require_auth)):
    return {"username": session["username"], "role": session["role"]}


# ── Frontend ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open(f"{_WEB_DIR}/Donna.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ── Status ────────────────────────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    try:
        alerts = len(db.get_active_escalations())
    except Exception:
        alerts = 0
    last_sync = datetime.now(_RIYADH_TZ).strftime("%Y-%m-%d %H:%M")
    return {
        "donna_active": True,
        "last_sync": last_sync,
        "alerts": alerts,
        "production_url": CONFIG.get("erpnext", {}).get("url", ""),
    }


# ── Finance endpoints ─────────────────────────────────────────────────────────
@app.get("/api/tools/overdue-invoices")
async def get_overdue_invoices():
    items = erp.get_overdue_invoices()
    total = sum(x.get("outstanding_amount", 0) for x in items)
    for x in items:
        try:
            x["days_late"] = (date.today() - date.fromisoformat(str(x["due_date"]))).days
        except Exception:
            x["days_late"] = 0
    return {"invoices": items, "total_exposure": round(total, 2), "count": len(items)}


@app.get("/api/tools/collections-tracker")
async def get_collections():
    items = db.get_active_escalations()
    return {"escalations": items, "count": len(items)}


@app.get("/api/tools/payables-summary")
async def get_payables():
    items = erp.get_overdue_payables()
    total = sum(x.get("outstanding_amount", 0) for x in items)
    for x in items:
        try:
            x["days_late"] = (date.today() - date.fromisoformat(str(x["due_date"]))).days
        except Exception:
            x["days_late"] = 0
    return {"payables": items, "total_owed": round(total, 2), "count": len(items)}


@app.get("/api/tools/daily-financial")
async def get_daily_financial():
    today = datetime.now(_RIYADH_TZ).date()
    invoices = erp.get_sales_invoices(days_back=7)
    payments = erp.get_payment_entries(days_back=7)
    overdue = erp.get_overdue_invoices()
    overdue_total = sum(x.get("outstanding_amount", 0) for x in overdue)
    proformas = erp.get_unconverted_proformas()
    proforma_total = sum(x.get("grand_total", 0) for x in proformas)
    return {
        "date": str(today),
        "invoices_this_week": len(invoices),
        "payments_this_week": len(payments),
        "overdue_count": len(overdue),
        "overdue_total": round(overdue_total, 2),
        "proforma_count": len(proformas),
        "proforma_total": round(proforma_total, 2),
    }


@app.get("/api/tools/pl-overview")
async def get_pl():
    try:
        invoices = erp.get_sales_invoices(days_back=30)
        purchases = erp.get_purchase_invoices(days_back=30)
        revenue = sum(x.get("grand_total", 0) for x in invoices if str(x.get("docstatus", "")) == "1")
        expenses = sum(x.get("grand_total", 0) for x in purchases if str(x.get("docstatus", "")) == "1")
        return {
            "period": "Last 30 days",
            "revenue": round(revenue, 2),
            "expenses": round(expenses, 2),
            "net": round(revenue - expenses, 2),
            "invoice_count": len(invoices),
            "purchase_count": len(purchases),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tools/payment-patterns")
async def get_payment_patterns():
    invoices = erp.get_sales_invoices(days_back=365, status="Paid")
    payments = erp.get_payment_entries(days_back=365)
    pay_map = {p["party"]: p["posting_date"] for p in payments}
    patterns: dict = {}
    for inv in invoices:
        cust = inv.get("customer")
        due = inv.get("due_date")
        if not cust or not due:
            continue
        pay_date_str = pay_map.get(cust, inv.get("posting_date", str(due)))
        try:
            days_to_pay = (date.fromisoformat(str(pay_date_str)) - date.fromisoformat(str(due))).days
            patterns.setdefault(cust, []).append(days_to_pay)
        except Exception:
            continue
    result = []
    for cust, vals in sorted(patterns.items(), key=lambda x: statistics.mean(x[1]), reverse=True):
        avg = statistics.mean(vals)
        result.append({
            "customer": cust,
            "avg_days_to_pay": round(avg, 1),
            "payments_count": len(vals),
            "status": "late" if avg > 5 else "on_time",
        })
    return {"patterns": result, "count": len(result)}


@app.get("/api/tools/proforma-conversions")
async def get_proformas():
    items = erp.get_unconverted_proformas()
    total = sum(x.get("grand_total", 0) for x in items)
    return {"proformas": items, "total_value": round(total, 2), "count": len(items)}


@app.get("/api/tools/zatca-status")
async def get_zatca():
    items = erp.get_zatca_rejections(since_hours=720)
    return {"issues": items, "count": len(items), "period_hours": 720}


# ── Tickets ───────────────────────────────────────────────────────────────────
@app.get("/api/tools/open-tickets")
async def get_open_tickets():
    items = erp.get_helpdesk_tickets(limit=100)
    return {"tickets": items, "count": len(items)}


@app.get("/api/tools/overdue-tickets")
async def get_overdue_tickets():
    all_open = erp.get_list(
        "HD Ticket",
        filters=[["status", "not in", ["Resolved", "Closed"]]],
        fields=["name", "subject", "priority", "creation", "_assign", "customer", "status"],
        limit=200,
    )
    with db._conn() as conn:
        sla_rows = conn.execute("SELECT * FROM sla_rules").fetchall()
    sla = {r["priority"]: dict(r) for r in sla_rows}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    breached = []
    for t in all_open:
        priority = t.get("priority", "Medium")
        if priority == "Not Assigned":
            priority = "Medium"
        rule = sla.get(priority, sla.get("Medium"))
        if not rule:
            continue
        try:
            created = datetime.fromisoformat(str(t["creation"]))
        except Exception:
            continue
        age_hours = (now - created).total_seconds() / 3600
        if age_hours > rule["resolution_sla_hours"]:
            t["age_hours"] = round(age_hours, 1)
            t["sla_hours"] = rule["resolution_sla_hours"]
            breached.append(t)
    return {"tickets": breached, "count": len(breached)}


class CreateTicketBody(BaseModel):
    title: str
    description: str = ""
    priority: str = "Medium"
    customer: Optional[str] = None


@app.post("/api/tools/create-ticket")
async def create_ticket(body: CreateTicketBody):
    result = erp.create_helpdesk_ticket(
        subject=body.title,
        description=body.description or body.title,
        priority=body.priority,
        customer=body.customer,
    )
    return {"ticket_name": result.get("name"), "status": "created"}


# ── Logs ──────────────────────────────────────────────────────────────────────
@app.get("/api/tools/suggestions-log")
async def get_suggestions():
    with db._conn() as conn:
        rows = conn.execute(
            "SELECT * FROM suggestions ORDER BY date_noticed DESC LIMIT 50"
        ).fetchall()
    return {"suggestions": [dict(r) for r in rows]}


@app.get("/api/tools/session-log")
async def get_session_log():
    try:
        with open("/opt/cloud_agent/SESSION_LOG.md", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Messaging ─────────────────────────────────────────────────────────────────
_ALLOWED_WA = {
    w["number"]
    for w in CONFIG.get("communication", {}).get("whatsapp_whitelist", [])
    if w.get("number")
}


class SendWaBody(BaseModel):
    to: str
    message: str
    ticket_id: Optional[str] = None
    intervention: bool = False  # bypass whitelist for human takeover sends


@app.post("/api/tools/send-whatsapp")
async def send_whatsapp_api(body: SendWaBody):
    # Intervention sends bypass the whitelist (human taking over customer conv)
    if not body.intervention and body.to not in _ALLOWED_WA:
        raise HTTPException(status_code=403, detail=f"{body.to} not on allowed list")
    result = erp.send_whatsapp(body.to, body.message)
    sent_name = result.get("name") if isinstance(result, dict) else None
    if body.intervention:
        db.log_customer_conversation(
            body.to, "outbound", body.message,
            handled_by="human",
            ticket_ref=body.ticket_id,
        )
    else:
        member_name = next(
            (m["name"] for m in CONFIG.get("team_members", []) if m.get("whatsapp") == body.to),
            body.to,
        )
        db.log_team_conversation(
            member_name, body.to, "outbound", body.message,
            ticket_ref=body.ticket_id,
            sent_wa_message_name=sent_name,
            delivery_status="sent",
        )
    return {"status": "sent", "doc_name": sent_name}


class LogHumanMessageBody(BaseModel):
    message: str
    direction: str = "outbound"
    handled_by: str = "human"


@app.post("/api/customers/{phone_number}/log-human-message")
async def log_human_message(phone_number: str, body: LogHumanMessageBody):
    """Log a human-sent message to customer_conversations."""
    from urllib.parse import unquote
    phone = unquote(phone_number)
    if not phone.startswith("+"):
        phone = "+" + phone
    try:
        db.log_customer_conversation(
            phone, body.direction, body.message,
            handled_by=body.handled_by,
        )
        return {"status": "logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SendEmailBody(BaseModel):
    to: str
    subject: str
    message: str


@app.post("/api/tools/send-email")
async def send_email_api(body: SendEmailBody):
    import google_client as gcal
    if not gcal.google_configured():
        raise HTTPException(status_code=503, detail="Google not configured")
    try:
        result = gcal.send_new_email(body.to, body.subject, body.message)
        return {"status": "sent", "message_id": result.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Team conversations ────────────────────────────────────────────────────────
@app.get("/api/team/conversations/{member_id}")
async def get_member_conversations(member_id: str):
    member_wa = None
    member_display = member_id
    # Search team_members first, then whatsapp_whitelist (covers admin like Talha)
    all_contacts = (
        CONFIG.get("team_members", []) +
        [{"name": w.get("name", ""), "whatsapp": w.get("number", "")}
         for w in CONFIG.get("communication", {}).get("whatsapp_whitelist", [])]
    )
    for m in all_contacts:
        name = m.get("name", "")
        wa = m.get("whatsapp", "")
        if member_id.lower() in name.lower() or wa == member_id:
            member_wa = wa
            member_display = name or member_id
            break
    if not member_wa and member_id.startswith("+"):
        member_wa = member_id
    if not member_wa:
        raise HTTPException(status_code=404, detail=f"Team member '{member_id}' not found")
    msgs = db.get_conversation_thread(member_wa, limit=50)
    return {"member": member_display, "whatsapp": member_wa, "messages": msgs, "count": len(msgs)}


@app.get("/api/team/members")
async def get_team_members():
    members = CONFIG.get("team_members", [])
    with db._conn() as conn:
        wa_rows = conn.execute(
            "SELECT contact_number, last_inbound_message_time, window_active FROM whatsapp_conversations"
        ).fetchall()
        # Also get last message time from team_conversations for members with no wa window record
        tc_rows = conn.execute(
            "SELECT whatsapp_number, MAX(timestamp) as last_ts FROM team_conversations GROUP BY whatsapp_number"
        ).fetchall()
    wa_status = {r["contact_number"]: dict(r) for r in wa_rows}
    tc_last = {r["whatsapp_number"]: r["last_ts"] for r in tc_rows}
    result = []
    for m in members:
        wa = m.get("whatsapp", "")
        ws = wa_status.get(wa, {})
        last_msg = ws.get("last_inbound_message_time", "") or tc_last.get(wa, "")
        result.append({
            "name": m.get("name"),
            "role": m.get("role", ""),
            "whatsapp": wa,
            "window_active": ws.get("window_active", 0),
            "last_message": last_msg,
        })
    return {"members": result, "count": len(result)}


# ── Customers ─────────────────────────────────────────────────────────────────
@app.get("/api/customers")
async def get_customers():
    """Return all customer contacts from the contacts table with last message + escalation info."""
    try:
        rows = db.get_all_customers_with_last_message()
        # Map escalation_status → sidebar color
        for r in rows:
            es = r.get("escalation_status")
            if es == "taken":
                r["status_color"] = "red"
            elif es == "pending":
                r["status_color"] = "orange"
            else:
                r["status_color"] = "green"
        return {"customers": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/customers/{phone_number}/conversation")
async def get_customer_conversation(phone_number: str):
    """Return customer_conversations for a phone number (URL-encoded + sign OK)."""
    # Normalise: allow %2B or raw +
    from urllib.parse import unquote
    phone = unquote(phone_number)
    if not phone.startswith("+"):
        phone = "+" + phone
    try:
        msgs = db.get_customer_conversation_history(phone, limit=50)
        contact = db.get_contact(phone)
        return {
            "customer": phone,
            "name": (contact or {}).get("name", phone),
            "company": (contact or {}).get("company", ""),
            "messages": msgs,
            "count": len(msgs),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Escalations ───────────────────────────────────────────────────────────────
@app.get("/api/escalations")
async def get_escalations():
    try:
        items = db.get_all_customer_escalations()
        return {"escalations": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TakeEscalationBody(BaseModel):
    agent_name: Optional[str] = "Admin"


@app.post("/api/escalations/{escalation_id}/take")
async def take_escalation(escalation_id: int, body: TakeEscalationBody):
    try:
        with db._conn() as conn:
            esc = conn.execute(
                "SELECT phone_number, customer_name FROM customer_escalations WHERE id=?",
                (escalation_id,),
            ).fetchone()
        if not esc:
            raise HTTPException(status_code=404, detail="Escalation not found")
        phone = esc["phone_number"]
        cname = esc["customer_name"] or phone
        db.resolve_customer_escalation(escalation_id, "taken")
        db.take_customer_escalation(phone, body.agent_name)
        # Notify customer
        try:
            import erpnext_client as _erp
            _erp.send_whatsapp(
                phone,
                "%s from BOT Solutions will assist you now." % body.agent_name,
            )
            db.log_customer_conversation(
                phone, "outbound",
                "%s joined the conversation." % body.agent_name,
                handled_by="human",
            )
        except Exception as e:
            pass  # Don't fail if WA send fails
        return {"status": "taken", "customer": cname, "phone": phone}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Chat ──────────────────────────────────────────────────────────────────────
class ChatBody(BaseModel):
    message: str
    thread: str = "admin"


@app.post("/api/chat")
async def chat(body: ChatBody):
    if _ask_claude_fn is None:
        raise HTTPException(status_code=503, detail="Chat backend not initialised yet")
    try:
        response = await _ask_claude_fn(
            body.message,
            channel="web",
            sender_name="Talha",
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
