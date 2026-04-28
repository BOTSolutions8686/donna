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
from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, "/opt/cloud_agent")

import logging as _logging
_log = _logging.getLogger("donna.web_api")
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


# ── Identity helper ──────────────────────────────────────────────────────────
def _display_name_for(username: str) -> str:
    """Derive a human first name from an ERPNext username/email."""
    import re as _re2
    # 1. donna_users table (authoritative)
    try:
        user_rec = db.get_donna_user(username)
        if user_rec and user_rec.get("display_name"):
            return user_rec["display_name"].split()[0]
    except Exception:
        pass
    # 2. team_members config by email
    for m in CONFIG.get("team_members", []):
        if m.get("email", "").lower() == username.lower():
            return m.get("name", username).split()[0]
    # 3. Email local-part
    if "@" in username:
        local = username.split("@")[0]
        name = _re2.sub(r"[^a-zA-Z]", "", local)
        return name.capitalize() if name else username
    return username


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


async def require_manager(session=Depends(_verify_token)):
    """Allow admin or manager."""
    if session.get("role") not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Manager access required")
    return session


def _check_permission(session: dict, permission: str):
    """Raise 403 if session user lacks permission. Falls back to role_permissions table."""
    username = session.get("username", "")
    if not db.has_permission(username, permission):
        raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")


# ── Auth endpoints ────────────────────────────────────────────────────────────
class LoginBody(BaseModel):
    username: str
    password: str



# ── PWA static assets ─────────────────────────────────────────────────────────

@app.get("/manifest.json")
async def serve_manifest():
    manifest = {
        "name": "Donna — Operations AI",
        "short_name": "Donna",
        "description": "BOT Solutions Operations AI Dashboard",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#060d1a",
        "theme_color": "#0ec4b4",
        "orientation": "portrait-primary",
        "icons": [
            {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Customers", "url": "/", "description": "View customer conversations"},
        ],
        "categories": ["business", "productivity"],
        "lang": "en",
        "scope": "/",
        "prefer_related_applications": False,
    }
    return JSONResponse(manifest, headers={
        "Content-Type": "application/manifest+json",
        "Cache-Control": "public, max-age=3600",
    })


@app.get("/sw.js")
async def serve_sw():
    sw = "const CACHE='donna-v4';\nconst SHELL=['/','/offline'];\n\nself.addEventListener('install',e=>{\n  e.waitUntil(\n    caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())\n  );\n});\n\nself.addEventListener('activate',e=>{\n  e.waitUntil(\n    caches.keys()\n      .then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k))))\n      .then(()=>self.clients.claim())\n  );\n});\n\nself.addEventListener('fetch',e=>{\n  const u=e.request.url;\n  if(u.includes('/api/')||u.includes('/auth')){\n    e.respondWith(\n      fetch(e.request).catch(()=>\n        new Response(JSON.stringify({error:'offline'}),\n          {headers:{'Content-Type':'application/json'}})\n      )\n    );\n    return;\n  }\n  if(e.request.mode==='navigate'){\n    e.respondWith(\n      fetch(e.request).then(r=>{\n        if(r&&r.ok){const c=r.clone();caches.open(CACHE).then(ca=>ca.put(e.request,c));}\n        return r;\n      }).catch(()=>\n        caches.match(e.request)\n          .then(r=>r||caches.match('/'))\n          .then(r=>r||caches.match('/offline'))\n      )\n    );\n    return;\n  }\n  e.respondWith(\n    caches.match(e.request).then(cached=>{\n      const network=fetch(e.request).then(r=>{\n        if(r&&r.ok&&r.type==='basic'){const c=r.clone();caches.open(CACHE).then(ca=>ca.put(e.request,c));}\n        return r;\n      });\n      return cached||network;\n    })\n  );\n});\n\nself.addEventListener('push',e=>{\n  if(!e.data) return;\n  let data;\n  try{ data=e.data.json(); }\n  catch{ data={title:'Donna',body:e.data.text(),url:'/'}; }\n  const title=data.title||'Donna — Operations AI';\n  const options={\n    body:data.body||'',\n    icon:data.icon||'/icon.svg',\n    badge:'/icon.svg',\n    tag:data.tag||'donna',\n    data:{url:data.url||'/'},\n    requireInteraction:false,\n    silent:false,\n    vibrate:[100,50,100],\n    timestamp:data.timestamp||Date.now(),\n    actions:[\n      {action:'open',title:'Open Donna'},\n      {action:'dismiss',title:'Dismiss'},\n    ]\n  };\n  e.waitUntil(self.registration.showNotification(title,options));\n});\n\nself.addEventListener('notificationclick',e=>{\n  e.notification.close();\n  if(e.action==='dismiss') return;\n  const url=e.notification.data?.url||'/';\n  e.waitUntil(\n    clients.matchAll({type:'window',includeUncontrolled:true}).then(cls=>{\n      for(const c of cls){\n        if(c.url.includes('donna.botsolutions.tech')&&'focus' in c){\n          return c.focus().then(wc=>wc.navigate(url));\n        }\n      }\n      if(clients.openWindow) return clients.openWindow('https://donna.botsolutions.tech'+url);\n    })\n  );\n});\n"
    return Response(sw, media_type="application/javascript", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
    })


@app.get("/icon.svg")
async def serve_icon_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<rect width="100" height="100" rx="22" fill="#060d1a"/>
<circle cx="50" cy="50" r="30" fill="none" stroke="#0ec4b4" stroke-width="5.5"/>
<text x="50" y="56" text-anchor="middle" font-family="system-ui,sans-serif"
  font-weight="700" font-size="34" fill="#0ec4b4">D</text>
</svg>"""
    return Response(svg, media_type="image/svg+xml", headers={
        "Cache-Control": "public, max-age=86400",
    })


@app.get("/icon-192.png")
async def serve_icon_192():
    return RedirectResponse("/icon.svg")

@app.get("/icon-512.png")
async def serve_icon_512():
    return RedirectResponse("/icon.svg")

@app.get("/offline")
async def serve_offline():
    body = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'/>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
        "<meta name='theme-color' content='#0ec4b4'/>"
        "<title>Donna — Offline</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0;}"
        "body{background:#060d1a;color:#7a96b8;font-family:system-ui,sans-serif;"
        "display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;}"
        ".card{text-align:center;max-width:320px;}"
        ".logo{width:64px;height:64px;border-radius:16px;background:#0ec4b4;"
        "display:flex;align-items:center;justify-content:center;margin:0 auto 20px;"
        "font-size:28px;font-weight:700;color:#060d1a;}"
        "h1{font-size:20px;font-weight:600;color:#e2eaf5;margin-bottom:8px;}"
        "p{font-size:14px;line-height:1.6;margin-bottom:20px;}"
        "button{background:#0ec4b4;color:#060d1a;border:none;border-radius:8px;"
        "padding:12px 24px;font-size:14px;font-weight:600;cursor:pointer;}"
        "</style></head><body>"
        "<div class='card'>"
        "<div class='logo'>D</div>"
        "<h1>Donna is Offline</h1>"
        "<p>No network connection right now. Check your signal and try again.</p>"
        "<button onclick='window.location.reload()'>Try Again</button>"
        "</div></body></html>"
    )
    return Response(body, media_type="text/html", headers={"Cache-Control": "no-store"})

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
        erpnext_role = "admin" if body.username in admin_users else "support"

        # Look up existing DB role — takes precedence over ERPNext default
        db_user = db.get_donna_user(body.username)
        if db_user and db_user.get('role') and db_user.get('role') not in ('agent', 'team'):
            role = db_user['role']
        else:
            role = erpnext_role

        _dn = _display_name_for(body.username)
        token = secrets.token_urlsafe(32)
        # Store correct role in session
        db.create_session(token, body.username, role, ttl_hours=24 * 7)  # 7-day sessions
        db.upsert_donna_user(body.username, display_name=_dn, role=erpnext_role)
        return {"token": token, "username": body.username, "role": role, "display_name": _dn}
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
    _dn = _display_name_for(session["username"])
    return {"username": session["username"], "role": session["role"], "display_name": _dn}


# ── Frontend ──────────────────────────────────────────────────────────────────


# ── WhatsApp webhook (Meta Cloud API via FastAPI) ─────────────────────────────
# Handles events on the main port (8080 → Caddy) — eliminates the need for a
# separate aiohttp server to be publicly reachable.


_wa_webhook_handler = None


def register_wa_webhook_handler(fn):
    """Called by cloud_agent at startup to register the processing callback."""
    global _wa_webhook_handler
    _wa_webhook_handler = fn
    _log.info("WhatsApp webhook handler registered (FastAPI port 8080)")


@app.get("/whatsapp-incoming")
async def wa_verify(request: Request):
    """Meta webhook verification challenge."""
    mode      = request.query_params.get("hub.mode", "")
    token     = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    expected  = CONFIG.get("meta_whatsapp", {}).get("webhook_verify_token", "")
    if mode == "subscribe" and token == expected and challenge:
        _log.info("Meta webhook verification OK (port 8080)")
        return Response(challenge, media_type="text/plain")
    _log.warning("Meta webhook verify failed: mode=%s match=%s", mode, token == expected)
    raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/whatsapp-incoming")
async def wa_inbound(request: Request):
    """Receive inbound WhatsApp events from Meta Cloud API (Donna dedicated app).

    Donna has its own Meta app — no fan-out to ERPNext needed.
    Flow: verify → ACK 200 immediately → dispatch to handlers in background.
    """
    import hmac as _hmac2, hashlib as _hashlib2, json as _wjson2, asyncio as _aio
    body_bytes = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if sig:
        app_secret = CONFIG.get("meta_whatsapp", {}).get("app_secret", "")
        if app_secret:
            expected = "sha256=" + _hmac2.new(app_secret.encode(), body_bytes, _hashlib2.sha256).hexdigest()
            if not _hmac2.compare_digest(sig, expected):
                _log.warning("Meta webhook HMAC mismatch")
                raise HTTPException(status_code=403, detail="Forbidden")
    else:
        # Legacy X-Donna-Secret relay (kept for backwards compat during transition)
        secret = request.headers.get("X-Donna-Secret", "")
        expected_s = CONFIG.get("whatsapp_webhook", {}).get("secret", "")
        if expected_s and secret != expected_s:
            raise HTTPException(status_code=403, detail="Forbidden")

    try:
        data = _wjson2.loads(body_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Bad JSON")

    if _wa_webhook_handler:
        _aio.get_event_loop().create_task(_wa_webhook_handler(data))
    else:
        _log.warning("wa_inbound: handler not registered yet")

    return Response(status_code=200)

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
async def get_pl(session=Depends(require_admin)):
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
        # Merge in conversation claims
        claims = {c["phone_number"]: c for c in db.get_all_claims()}
        for r in rows:
            phone = r.get("phone") or r.get("phone_number", "")
            cl = claims.get(phone)
            if cl:
                r["claimed_by"] = cl.get("claimed_by")
                r["claimed_by_name"] = cl.get("claimed_by_name")
                r["donna_paused"] = 1
                if r.get("status_color") == "green":
                    r["status_color"] = "orange"  # amber = human claimed
            else:
                r["claimed_by"] = None
                r["claimed_by_name"] = None
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






# ── Contacts ──────────────────────────────────────────────────────────────────

@app.get("/api/contacts/{phone}")
async def get_contact_detail(phone: str, session=Depends(require_auth)):
    """Get full contact detail including conversation count."""
    from urllib.parse import unquote
    phone = unquote(phone)
    with db._conn() as conn:
        row = conn.execute("SELECT * FROM contacts WHERE phone_number=?", (phone,)).fetchone()
        count = conn.execute(
            "SELECT COUNT(*) FROM customer_conversations WHERE customer_phone=?", (phone,)
        ).fetchone()[0]
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    contact = dict(row)
    contact['message_count'] = count
    return JSONResponse(contact)


@app.put("/api/contacts/{phone}")
async def update_contact(phone: str, request: Request, session=Depends(require_auth)):
    """Update a contact name, company, type, and flag from the UI."""
    from urllib.parse import unquote
    phone = unquote(phone)
    try:
        body = await request.json()
        name = body.get('name', '').strip()
        company = body.get('company', '').strip()
        contact_type = body.get('contact_type', 'customer')
        flagged = int(body.get('flagged', 0))
        flag_reason = body.get('flag_reason', '')
        with db._conn() as conn:
            conn.execute("""
                UPDATE contacts SET
                    name=COALESCE(NULLIF(?,\'\'),name),
                    company=COALESCE(NULLIF(?,\'\'),company),
                    contact_type=?,
                    flagged=?,
                    flag_reason=COALESCE(NULLIF(?,\'\'),flag_reason)
                WHERE phone_number=?
            """, (name, company, contact_type, flagged, flag_reason, phone))
        return JSONResponse({'ok': True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── EOD Reports ───────────────────────────────────────────────────────────────



# ── Web Push ──────────────────────────────────────────────────────────────────

@app.get("/api/push/vapid-public-key")
async def get_vapid_public_key():
    """Return VAPID public key for client-side subscription setup."""
    push_cfg = CONFIG.get("push_notifications", {})
    pub_key = push_cfg.get("vapid_public_key", "")
    if not pub_key:
        raise HTTPException(status_code=503, detail="Push not configured")
    return JSONResponse({"publicKey": pub_key})


@app.post("/api/push/subscribe")
async def subscribe_push(request: Request, session=Depends(require_auth)):
    """Save a push subscription from the PWA."""
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        body = await request.json()
        subscription = body.get("subscription", {})
        endpoint = subscription.get("endpoint", "")
        keys = subscription.get("keys", {})
        p256dh = keys.get("p256dh", "")
        auth = keys.get("auth", "")
        if not endpoint or not p256dh or not auth:
            raise HTTPException(status_code=400, detail="Invalid subscription")
        user_name = session.get("username", "unknown") if isinstance(session, dict) else "unknown"
        db.save_push_subscription(endpoint, p256dh, auth, user_name)
        _log.info("Push subscription saved for %s", user_name)
        return JSONResponse({"ok": True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/push/unsubscribe")
async def unsubscribe_push(request: Request, session=Depends(require_auth)):
    """Remove a push subscription."""
    try:
        body = await request.json()
        endpoint = body.get("endpoint", "")
        if endpoint:
            db.delete_push_subscription(endpoint)
        return JSONResponse({"ok": True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ── WhatsApp / Meta Settings ──────────────────────────────────────────────────

import logging as _wa_settings_log
_wslog = _wa_settings_log.getLogger("donna.settings")


def _persist_config_field(field: str, value):
    """Update a CONFIG field in memory. Manual config.py edit required to persist across restart."""
    _wslog.info("Config field '%s' updated in memory. Edit config.py to persist.", field)


@app.get("/api/settings/whatsapp")
async def get_whatsapp_settings(session=Depends(require_auth)):
    cfg = CONFIG.get("meta_whatsapp", {})
    token = cfg.get("access_token", "")
    token_preview = (token[:6] + "..." + token[-6:]) if len(token) > 12 else ("***" if token else "(not set)")
    return JSONResponse({
        "phone_number_id": cfg.get("phone_number_id", ""),
        "app_id": cfg.get("app_id", ""),
        "business_id": cfg.get("business_id", ""),
        "api_version": cfg.get("api_version", "v23.0"),
        "base_url": cfg.get("base_url", "https://graph.facebook.com"),
        "token_preview": token_preview,
        "webhook_verify_token": cfg.get("webhook_verify_token", ""),
        "webhook_url": "https://donna.botsolutions.tech/whatsapp-incoming",
    })


@app.post("/api/settings/whatsapp")
async def update_whatsapp_settings(request: Request, session=Depends(require_auth)):
    """Update Meta WABA settings. Token field only updates if non-empty."""
    role = session.get("role", "") if isinstance(session, dict) else ""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        body = await request.json()
        cfg = CONFIG.get("meta_whatsapp", {})
        for field in ["phone_number_id", "app_id", "business_id",
                      "api_version", "base_url", "webhook_verify_token"]:
            if body.get(field):
                cfg[field] = body[field]
        if body.get("access_token") and len(body["access_token"]) > 20:
            cfg["access_token"] = body["access_token"]
        CONFIG["meta_whatsapp"] = cfg
        _persist_config_field("meta_whatsapp", cfg)
        return JSONResponse({"ok": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/whatsapp/test")
async def test_whatsapp_connection(session=Depends(require_auth)):
    """Test Meta WABA connection by fetching phone number info."""
    try:
        cfg = CONFIG.get("meta_whatsapp", {})
        version = cfg.get("api_version", "v23.0")
        phone_id = cfg.get("phone_number_id", "")
        base = cfg.get("base_url", "https://graph.facebook.com")
        token = cfg.get("access_token", "")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{base}/{version}/{phone_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "display_phone_number,verified_name,quality_rating"},
            )
        if r.status_code == 200:
            data = r.json()
            return JSONResponse({
                "ok": True,
                "display_phone_number": data.get("display_phone_number", ""),
                "verified_name": data.get("verified_name", ""),
                "quality_rating": data.get("quality_rating", ""),
            })
        return JSONResponse({
            "ok": False,
            "error": f"API returned {r.status_code}: {r.text[:100]}",
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})



# ── Siri Shortcut ─────────────────────────────────────────────────────────────

import logging as _logging
import re as _re
import time as _time

_shortcut_log = _logging.getLogger("donna.shortcut")

# Simple in-memory rate limiter: max 10 requests/minute per IP
_shortcut_hits: dict = {}
_SHORTCUT_MAX_RPM = 10

def _shortcut_rate_ok(ip: str) -> bool:
    now = _time.time()
    hits = [t for t in _shortcut_hits.get(ip, []) if now - t < 60]
    _shortcut_hits[ip] = hits
    if len(hits) >= _SHORTCUT_MAX_RPM:
        return False
    _shortcut_hits[ip].append(now)
    return True


def _verify_shortcut_key(request: Request) -> bool:
    key = request.headers.get("X-Shortcut-Key", "")
    expected = CONFIG.get("shortcuts", {}).get("api_key", "")
    return bool(expected) and key == expected


@app.post("/api/shortcut/ask")
async def shortcut_ask(request: Request):
    """
    Siri Shortcut endpoint. Accepts JSON {"question": "..."}.
    Returns plain text so Siri can speak it directly.
    Authenticated via X-Shortcut-Key header — no session cookie needed.
    """
    if not _verify_shortcut_key(request):
        return Response("Authentication failed.", media_type="text/plain", status_code=403)

    _client_ip = request.client.host if request.client else "unknown"
    if not _shortcut_rate_ok(_client_ip):
        _shortcut_log.warning("Shortcut rate limit hit from %s", _client_ip)
        return Response("Rate limit exceeded. Try again shortly.", media_type="text/plain", status_code=429)

    if _ask_claude_fn is None:
        return Response("Donna is starting up. Try again in a moment.", media_type="text/plain")

    try:
        body = await request.json()
        question = (body.get("question") or "").strip()
        if not question:
            return Response(
                "I didn't catch a question. Please try again.",
                media_type="text/plain",
            )

        _shortcut_log.info("Shortcut query: %s", question[:120])

        # Reuse the same full-tools admin pipeline as Telegram/web
        response_text = await _ask_claude_fn(
            question,
            channel="shortcut",
            sender_name="Talha",
        )

        # Strip markdown for clean voice playback
        clean = _re.sub(r'\*\*([^*]+)\*\*', r'\1', response_text)
        clean = _re.sub(r'\*([^*]+)\*', r'\1', clean)
        clean = _re.sub(r'`([^`]+)`', r'\1', clean)
        clean = _re.sub(r'#{1,6}\s+', '', clean)
        clean = clean.replace('—', ',').replace('|', ',')
        clean = _re.sub(r'  +', ' ', clean)

        # Trim to ~120 words — comfortable Siri voice length
        words = clean.split()
        if len(words) > 120:
            clean = ' '.join(words[:120]) + '. For more details, check the Donna dashboard.'

        return Response(clean.strip(), media_type="text/plain")

    except Exception as e:
        _shortcut_log.error("shortcut_ask error: %s", e, exc_info=True)
        return Response(
            "Sorry, I ran into an error. Please check the Donna dashboard.",
            media_type="text/plain",
        )



# ── Admin conversation (cross-device chat history) ────────────────────────────

@app.get("/api/admin/conversation")
async def get_admin_conversation_api(session=Depends(require_auth)):
    username = session.get("username", "admin") if isinstance(session, dict) else "admin"
    msgs = db.get_admin_conversation(username, limit=50)
    return JSONResponse({"messages": msgs})


@app.post("/api/admin/conversation/log")
async def log_admin_message_api(request: Request, session=Depends(require_auth)):
    username = session.get("username", "admin") if isinstance(session, dict) else "admin"
    try:
        body = await request.json()
        direction = body.get("direction", "outbound")
        content = body.get("content", "")
        if content:
            db.log_admin_message(username, direction, content)
        return JSONResponse({"ok": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Notifications ─────────────────────────────────────────────────────────────

@app.get("/api/notifications")
async def get_notifications_api(unread: str = "0", session=Depends(require_auth)):
    unread_only = unread == "1"
    notifs = db.get_notifications(limit=20, unread_only=unread_only)
    unread_count = sum(1 for n in notifs if not n["read"])
    return JSONResponse({"notifications": notifs, "unread": unread_count})


@app.post("/api/notifications/read")
async def mark_notifications_read_api(session=Depends(require_auth)):
    db.mark_notifications_read()
    return JSONResponse({"ok": True})


@app.delete("/api/notifications/{notif_id}")
async def delete_notification_api(notif_id: int, session=Depends(require_auth)):
    db.delete_notification(notif_id)
    return JSONResponse({"ok": True})


@app.post("/api/notifications/clear-all")
async def clear_all_notifications_api(session=Depends(require_auth)):
    db.clear_all_notifications()
    return JSONResponse({"ok": True})


# ── Push test ─────────────────────────────────────────────────────────────────

_send_push_fn = None


def set_send_push(fn):
    global _send_push_fn
    _send_push_fn = fn


@app.post("/api/push/test")
async def test_push_notification(session=Depends(require_auth)):
    role = session.get("role", "") if isinstance(session, dict) else ""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if _send_push_fn is None:
        raise HTTPException(status_code=503, detail="Push backend not initialised")
    try:
        await _send_push_fn(
            title="🔔 Donna Test Notification",
            body="Push notifications are working! You will receive alerts for escalations, ZATCA issues, and EOD reports.",
            url="/",
            tag="test",
        )
        return JSONResponse({"ok": True, "message": "Test push sent to all subscribed devices"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




# ── User management (admin only) ──────────────────────────────────────────────

VALID_ROLES = {"admin", "manager", "support", "viewer"}

ROLE_LABELS = {
    "admin":   "Admin — full access",
    "manager": "Manager — reports + customers, no settings",
    "support": "Support — customer tickets + WhatsApp",
    "viewer":  "Viewer — read-only dashboard",
}


@app.get("/api/users")
async def list_users_api(session=Depends(require_admin)):
    users = db.list_donna_users()
    return {"users": users, "roles": ROLE_LABELS}


class UserRoleBody(BaseModel):
    role: str


class UserNameBody(BaseModel):
    display_name: str


@app.patch("/api/users/{username}/role")
async def set_user_role(username: str, body: UserRoleBody, session=Depends(require_admin)):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {sorted(VALID_ROLES)}")
    admin_users = _get_admin_users()
    if username in admin_users and body.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot change role of primary admin")
    db.update_donna_user_role(username, body.role)
    return {"ok": True, "username": username, "role": body.role}


@app.patch("/api/users/{username}/whatsapp")
async def update_user_whatsapp_number(username: str, body: dict, session=Depends(require_auth)):
    """Set a user's WhatsApp number. Users can set their own; admins can set anyone's."""
    caller = session.get("username", "")
    if caller != username and session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    wa = (body.get("whatsapp_number") or "").strip()
    db.set_donna_user_whatsapp(username, wa or None)
    return {"ok": True, "username": username, "whatsapp_number": wa or None}

@app.patch("/api/users/{username}/name")
async def set_user_display_name(username: str, body: UserNameBody, session=Depends(require_admin)):
    db.update_donna_user_name(username, body.display_name)
    return {"ok": True, "username": username, "display_name": body.display_name}


@app.patch("/api/users/{username}/deactivate")
async def deactivate_user_api(username: str, session=Depends(require_admin)):
    admin_users = _get_admin_users()
    if username in admin_users:
        raise HTTPException(status_code=403, detail="Cannot deactivate primary admin")
    db.deactivate_donna_user(username)
    return {"ok": True}


@app.patch("/api/users/{username}/activate")
async def activate_user_api(username: str, session=Depends(require_admin)):
    db.activate_donna_user(username)
    return {"ok": True}

@app.get("/api/reports/daily")
async def get_daily_reports_api(date: str = None, session=Depends(require_auth)):
    from datetime import date as _date
    report_date = date or _date.today().isoformat()
    reports = db.get_daily_reports(report_date=report_date)
    return {"reports": reports, "date": report_date, "count": len(reports)}


@app.get("/api/reports/member/{whatsapp}")
async def get_member_reports_api(whatsapp: str, session=Depends(require_auth)):
    import urllib.parse
    wa_decoded = urllib.parse.unquote(whatsapp)
    reports = db.get_member_report_history(wa_decoded, limit=10)
    return {"reports": reports, "whatsapp": wa_decoded, "count": len(reports)}

# ── Chat ──────────────────────────────────────────────────────────────────────
class ChatBody(BaseModel):
    message: str
    thread: str = "admin"


@app.post("/api/chat")
async def chat(body: ChatBody, session=Depends(require_auth)):
    if _ask_claude_fn is None:
        raise HTTPException(status_code=503, detail="Chat backend not initialised yet")
    username = session.get("username", "admin") if isinstance(session, dict) else "admin"
    try:
        _display = _display_name_for(username)
        _user_role = session.get("role", "support") if isinstance(session, dict) else "support"
        response = await _ask_claude_fn(
            body.message,
            channel="web",
            sender_name=_display,
            sender_role=_user_role,
        )
        try:
            db.log_admin_message(username, "inbound", body.message)
            db.log_admin_message(username, "outbound", response)
        except Exception:
            pass
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Calendar API ──────────────────────────────────────────────────────────────

@app.get("/api/calendar/events")
async def get_calendar_events(days: int = 7, session=Depends(require_auth)):
    """Return upcoming calendar events (uses admin Google account)."""
    _check_permission(session, "view_calendar")
    try:
        import google_client as _gc
        if not _gc.google_configured():
            return {"events": [], "error": "Google Calendar not configured"}
        events = _gc.get_upcoming_events(days_ahead=days, max_results=30)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CalendarEventBody(BaseModel):
    title: str
    start: str          # ISO datetime, e.g. "2026-04-29T10:00:00"
    end: str            # ISO datetime
    description: str = ""
    attendees: list = []
    location: str = ""
    with_meet: bool = False

@app.post("/api/calendar/events")
async def create_calendar_event(body: CalendarEventBody, session=Depends(require_auth)):
    """Create a calendar event (optionally with Google Meet)."""
    _check_permission(session, "view_calendar")
    try:
        import google_client as _gc
        if not _gc.google_configured():
            raise HTTPException(status_code=400, detail="Google Calendar not configured")
        if body.with_meet:
            result = _gc.create_event_with_meet(
                title=body.title,
                start_dt=body.start,
                end_dt=body.end,
                description=body.description,
                attendees=body.attendees or None,
            )
        else:
            result = _gc.create_event(
                title=body.title,
                start_dt=body.start,
                end_dt=body.end,
                description=body.description,
                attendees=body.attendees or None,
                location=body.location,
            )
        return {"ok": True, "event": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/calendar/events/{event_id}")
async def delete_calendar_event(event_id: str, session=Depends(require_auth)):
    """Delete a calendar event."""
    _check_permission(session, "view_calendar")
    try:
        import google_client as _gc
        svc = _gc._calendar()
        svc.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Per-user Gmail OAuth ──────────────────────────────────────────────────────
# Uses Google Device Authorization Flow (no browser on server needed).
# UI: 1) call /start → get {user_code, verification_url, device_code}
#     2) user opens URL, enters code on their phone
#     3) UI polls /poll with device_code until connected

_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

@app.get("/api/oauth/google/start")
async def oauth_google_start(session=Depends(require_auth)):
    """Initiate Device Authorization Flow for Gmail. Returns user_code + verification_url."""
    try:
        from config import CONFIG as _cfg
        gcfg = _cfg.get("google", {})
        client_id = gcfg.get("client_id", "")
        if not client_id:
            raise HTTPException(status_code=400, detail="Google OAuth not configured (no client_id in config)")
        import httpx as _hx
        resp = _hx.post(
            "https://oauth2.googleapis.com/device/code",
            data={
                "client_id": client_id,
                "scope": " ".join(_GMAIL_SCOPES),
            },
            timeout=15,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Google API error: {resp.text[:200]}")
        data = resp.json()
        return {
            "device_code": data["device_code"],
            "user_code": data["user_code"],
            "verification_url": data["verification_url"],
            "expires_in": data.get("expires_in", 1800),
            "interval": data.get("interval", 5),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/oauth/google/poll")
async def oauth_google_poll(body: dict, session=Depends(require_auth)):
    """Poll Device Authorization Flow for completion. Call every `interval` seconds."""
    device_code = body.get("device_code", "")
    if not device_code:
        raise HTTPException(status_code=400, detail="device_code required")
    try:
        from config import CONFIG as _cfg
        gcfg = _cfg.get("google", {})
        import httpx as _hx
        resp = _hx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": gcfg.get("client_id", ""),
                "client_secret": gcfg.get("client_secret", ""),
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            if data["error"] == "authorization_pending":
                return {"status": "pending"}
            if data["error"] == "slow_down":
                return {"status": "slow_down"}
            return {"status": "error", "detail": data.get("error_description", data["error"])}
        # Success — fetch email address
        access_token = data["access_token"]
        refresh_token = data.get("refresh_token", "")
        import json as _json
        token_json = _json.dumps(data)
        # Get the Gmail email address
        email_resp = _hx.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        email_addr = email_resp.json().get("email", "") if email_resp.status_code == 200 else ""
        username = session.get("username", "")
        db.save_user_integration(username, "gmail", token_json, email_address=email_addr, scopes=" ".join(_GMAIL_SCOPES))
        return {"status": "connected", "email": email_addr}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/oauth/google")
async def oauth_google_disconnect(session=Depends(require_auth)):
    """Disconnect the user's Gmail integration."""
    username = session.get("username", "")
    db.remove_user_integration(username, "gmail")
    return {"ok": True}

@app.get("/api/oauth/status")
async def oauth_status(session=Depends(require_auth)):
    """Return which OAuth integrations the current user has connected."""
    username = session.get("username", "")
    integrations = db.list_user_integrations(username)
    return {"integrations": integrations}

# ── Per-user Gmail inbox / drafting ───────────────────────────────────────────

def _user_gmail_creds(username: str):
    """Build Google Credentials from user's stored token. Raises if not connected."""
    row = db.get_user_integration(username, "gmail")
    if not row:
        raise HTTPException(status_code=400, detail="Gmail not connected. Connect first via /api/oauth/google/start")
    import json as _json
    from config import CONFIG as _cfg
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    data = _json.loads(row["token_json"])
    gcfg = _cfg.get("google", {})
    creds = Credentials(
        token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=gcfg.get("client_id", ""),
        client_secret=gcfg.get("client_secret", ""),
        scopes=_GMAIL_SCOPES,
    )
    if creds.expired or not creds.valid:
        creds.refresh(Request())
        # Persist refreshed token
        new_data = dict(data)
        new_data["access_token"] = creds.token
        db.save_user_integration(username, "gmail", _json.dumps(new_data),
                                  email_address=row.get("email_address"),
                                  scopes=row.get("scopes"))
    return creds

@app.get("/api/email/inbox")
async def get_user_email_inbox(session=Depends(require_auth), limit: int = 20):
    """Fetch the logged-in user's unread emails via their connected Gmail."""
    _check_permission(session, "view_email")
    username = session.get("username", "")
    try:
        from googleapiclient.discovery import build
        creds = _user_gmail_creds(username)
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        result = svc.users().messages().list(
            userId="me", labelIds=["INBOX"], q="is:unread", maxResults=limit
        ).execute()
        emails = []
        for msg_ref in result.get("messages", []):
            try:
                msg = svc.users().messages().get(userId="me", id=msg_ref["id"], format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"]).execute()
                hdrs = {h["name"].lower(): h["value"]
                        for h in msg.get("payload", {}).get("headers", [])}
                emails.append({
                    "message_id": msg["id"],
                    "thread_id": msg.get("threadId", ""),
                    "from": hdrs.get("from", ""),
                    "subject": hdrs.get("subject", "(no subject)"),
                    "date": hdrs.get("date", ""),
                    "snippet": msg.get("snippet", "")[:200],
                })
            except Exception:
                pass
        return {"emails": emails, "total": len(emails)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class EmailDraftBody(BaseModel):
    message_id: str
    thread_id: str
    from_addr: str
    subject: str
    snippet: str

@app.post("/api/email/draft")
async def draft_email_reply(body: EmailDraftBody, session=Depends(require_auth)):
    """Ask Donna to draft a reply to an email. Returns draft text."""
    _check_permission(session, "view_email")
    if _ask_claude_fn is None:
        raise HTTPException(status_code=503, detail="Chat backend not initialised")
    username = session.get("username", "")
    sender_name = _display_name_for(username)
    sender_role = session.get("role", "support")
    prompt = (
        f"Draft a professional email reply to this message.\n\n"
        f"From: {body.from_addr}\n"
        f"Subject: {body.subject}\n"
        f"Message preview: {body.snippet}\n\n"
        f"Write only the reply body (no salutation line or signature — I will add those). "
        f"Be concise and professional. Reply in the same language as the original message."
    )
    reply_text = await _ask_claude_fn(prompt, channel="web", sender_name=sender_name, sender_role=sender_role)
    return {
        "draft": reply_text,
        "thread_id": body.thread_id,
        "to": body.from_addr,
        "subject": ("Re: " + body.subject) if not body.subject.startswith("Re:") else body.subject,
    }

class EmailSendBody(BaseModel):
    thread_id: str
    to: str
    subject: str
    body: str

@app.post("/api/email/send")
async def send_email_reply(body: EmailSendBody, session=Depends(require_auth)):
    """Send an email reply using the user's connected Gmail account."""
    _check_permission(session, "send_email_draft")
    username = session.get("username", "")
    try:
        from googleapiclient.discovery import build
        from email.mime.text import MIMEText
        import base64 as _b64
        creds = _user_gmail_creds(username)
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        msg = MIMEText(body.body)
        msg["To"] = body.to
        msg["Subject"] = body.subject
        raw = _b64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = svc.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": body.thread_id},
        ).execute()
        return {"ok": True, "message_id": sent.get("id"), "to": body.to}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Role Permissions API ──────────────────────────────────────────────────────

ALL_PERMISSIONS = [
    "view_financials", "view_reports", "manage_users", "manage_roles",
    "manage_settings", "view_customers", "chat_customers", "send_whatsapp",
    "claim_conversation", "view_eod_summary", "view_calendar", "view_email",
    "escalate_tickets", "view_team_chat", "send_email_draft",
]

PERMISSION_LABELS = {
    "view_financials":    "View financial data (P&L, overdue invoices)",
    "view_reports":       "View EOD & team reports",
    "manage_users":       "Create & manage users",
    "manage_roles":       "Edit role permissions",
    "manage_settings":    "Change app settings",
    "view_customers":     "View customer list & conversations",
    "chat_customers":     "Send messages to customers",
    "send_whatsapp":      "Send outbound WhatsApp messages",
    "claim_conversation": "Claim/take over customer conversations",
    "view_eod_summary":   "Receive EOD team summary",
    "view_calendar":      "Access calendar integration",
    "view_email":         "Access email integration",
    "escalate_tickets":   "Escalate support tickets",
    "view_team_chat":     "View team WhatsApp conversations",
    "send_email_draft":   "Draft & send emails (with approval)",
}

@app.get("/api/permissions")
async def get_permissions(session=Depends(require_admin)):
    """Return full permission matrix for all roles."""
    matrix = db.get_all_role_permissions()
    return {
        "matrix": matrix,
        "permissions": ALL_PERMISSIONS,
        "labels": PERMISSION_LABELS,
    }


class PermissionUpdateBody(BaseModel):
    role: str
    permission: str
    granted: bool


@app.patch("/api/permissions")
async def update_permission(body: PermissionUpdateBody, session=Depends(require_admin)):
    """Toggle a single permission flag for a role."""
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if body.permission not in ALL_PERMISSIONS:
        raise HTTPException(status_code=400, detail="Invalid permission")
    if body.role == "admin":
        raise HTTPException(status_code=400, detail="Admin always has full permissions")
    db.set_role_permission(body.role, body.permission, body.granted)
    return {"ok": True, "role": body.role, "permission": body.permission, "granted": body.granted}


# ── Pre-create user endpoint ──────────────────────────────────────────────────

class CreateUserBody(BaseModel):
    username: str
    display_name: str
    role: str = "support"


@app.post("/api/users")
async def create_user_api(body: CreateUserBody, session=Depends(require_admin)):
    """Pre-create a user before first login."""
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {sorted(VALID_ROLES)}")
    ok = db.create_donna_user_manual(body.username, body.display_name, body.role)
    if not ok:
        raise HTTPException(status_code=409, detail="User already exists")
    return {"ok": True, "username": body.username, "display_name": body.display_name, "role": body.role}


# ── Conversation Claiming ─────────────────────────────────────────────────────

@app.post("/api/customers/{phone_number}/claim")
async def claim_conversation_api(phone_number: str, session=Depends(require_auth)):
    """Claim a customer conversation for human handling (pauses Donna AI)."""
    _check_permission(session, "claim_conversation")
    username = session.get("username", "")
    display_name = _display_name_for(username)
    ok = db.claim_conversation(phone_number, username, display_name)
    if not ok:
        existing = db.get_conversation_claim(phone_number)
        raise HTTPException(status_code=409, detail=f"Already claimed by {existing.get('claimed_by_name', existing.get('claimed_by'))}")
    try:
        import cloud_agent as _ca_mod
        import asyncio as _claim_aio
        _claim_aio.get_event_loop().create_task(
            _ca_mod._send_claim_handoff_summary(username, phone_number)
        )
    except Exception as _hs_err:
        _log.debug("Handoff summary trigger error: %s", _hs_err)
    return {"ok": True, "phone_number": phone_number, "claimed_by": username, "claimed_by_name": display_name}


@app.post("/api/customers/{phone_number}/release")
async def release_conversation_api(phone_number: str, session=Depends(require_auth)):
    """Release a claimed conversation back to Donna."""
    username = session.get("username", "")
    role = session.get("role", "support")
    claim = db.get_conversation_claim(phone_number)
    if claim and claim.get("claimed_by") != username and role != "admin":
        raise HTTPException(status_code=403, detail="You can only release your own claims")
    db.release_conversation(phone_number, username)
    # After release, check if the last message was inbound — if so, Donna replies
    try:
        history = db.get_customer_conversation_history(phone_number, limit=5)
        if history and history[-1].get("direction") == "inbound":
            last_msg = history[-1].get("message_content", "")
            import cloud_agent as _ca_rel
            import asyncio as _rel_aio
            _rel_aio.get_event_loop().create_task(
                _ca_rel.handle_customer_message(phone_number, last_msg, wa_name=None)
            )
            _log.info("release: queued Donna reply to %s after human release", phone_number)
    except Exception as _rel_err:
        _log.debug("release post-check error: %s", _rel_err)
    return {"ok": True, "phone_number": phone_number}


@app.get("/api/conversations/claims")
async def get_claims_api(session=Depends(require_auth)):
    """Return all active conversation claims."""
    return {"claims": db.get_all_claims()}


# ── Ticket from chat ──────────────────────────────────────────────────────────

class TicketDraftBody(BaseModel):
    phone_number: str
    message_content: str

class TicketCreateBody(BaseModel):
    phone_number: str
    title: str
    description: str
    priority: str = "Medium"

@app.post("/api/tickets/draft-from-message")
async def draft_ticket_from_message(body: TicketDraftBody, session=Depends(require_auth)):
    """Use Claude to draft a ticket title/description from a customer message."""
    _check_permission(session, "view_customers")
    try:
        import anthropic as _ant2
        client = _ant2.Anthropic(api_key=CONFIG["anthropic"]["api_key"])
        contact = db.get_contact(body.phone_number)
        cname = (contact or {}).get("name") or body.phone_number
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=(
                "You extract support ticket fields from a WhatsApp message. "
                "Reply ONLY with a JSON object with keys: title (max 60 chars), "
                "description (1-2 sentences), priority (Low/Medium/High/Urgent). "
                "No markdown, no extra text."
            ),
            messages=[{"role": "user", "content": (
                f"Customer: {cname}\nMessage: {body.message_content}"
            )}],
        )
        import json as _jdraft
        raw = resp.content[0].text.strip()
        # strip possible markdown fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = _jdraft.loads(raw)
        return {
            "title": data.get("title", body.message_content[:60]),
            "description": data.get("description", body.message_content),
            "priority": data.get("priority", "Medium"),
        }
    except Exception as e:
        _log.warning("draft_ticket_from_message: %s", e)
        return {
            "title": body.message_content[:60],
            "description": body.message_content,
            "priority": "Medium",
        }

@app.post("/api/tickets/create-from-chat")
async def create_ticket_from_chat(body: TicketCreateBody, session=Depends(require_auth)):
    """Create an ERPNext ticket from chat and send WA confirmation to customer."""
    _check_permission(session, "view_customers")
    try:
        result = erp.create_ticket(
            subject=body.title,
            description=body.description,
            priority=body.priority,
        )
        ticket_name = result.get("name", "")
        # Link ticket reference to customer conversation
        if ticket_name:
            db.upsert_contact(body.phone_number, contact_type=None)
        # Send WhatsApp confirmation to customer
        confirm_msg = (
            f"Your request has been logged as support ticket {ticket_name}. "
            f"Our team will follow up with you shortly. ✓"
        )
        try:
            erp.send_whatsapp(body.phone_number, confirm_msg)
            db.log_customer_conversation(
                body.phone_number, "outbound", confirm_msg,
                ticket_ref=ticket_name, handled_by="donna",
            )
        except Exception as _we:
            _log.warning("Ticket WA confirmation failed: %s", _we)
        return {"ok": True, "ticket_name": ticket_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Outbound WhatsApp Composer ────────────────────────────────────────────────

class OutboundWABody(BaseModel):
    phone_number: str
    message: str
    template_name: str = None
    template_params: list = None


_send_whatsapp_fn = None

def register_send_whatsapp(fn):
    """Register the function that sends WhatsApp messages (from cloud_agent)."""
    global _send_whatsapp_fn
    _send_whatsapp_fn = fn


@app.post("/api/whatsapp/send")
async def send_whatsapp_outbound(body: OutboundWABody, session=Depends(require_auth)):
    """Send an outbound WhatsApp message to any phone number."""
    _check_permission(session, "send_whatsapp")
    if _send_whatsapp_fn is None:
        raise HTTPException(status_code=503, detail="WhatsApp sender not initialised")

    phone = body.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    username = session.get("username", "")
    sender_name = _display_name_for(username)

    try:
        if body.template_name:
            await _send_whatsapp_fn(phone, None, template_name=body.template_name, template_params=body.template_params or [])
        else:
            await _send_whatsapp_fn(phone, body.message)

        # Log the outbound message
        try:
            import database as _db2
            with _db2._conn() as conn:
                conn.execute("""
                    INSERT INTO customer_conversations
                        (phone_number, direction, message_content, handled_by)
                    VALUES (?, 'outbound', ?, ?)
                    ON CONFLICT DO NOTHING
                """, (phone, body.message or f"[template:{body.template_name}]", sender_name))
        except Exception:
            pass

        return {"ok": True, "to": phone, "sender": sender_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/whatsapp/templates")
async def list_wa_templates(session=Depends(require_auth)):
    """Return approved WhatsApp message templates from Meta."""
    try:
        import erpnext_client as _erp
        templates = _erp.get_whatsapp_templates(limit=50)
        return {"templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/whatsapp/check-window/{phone_number}")
async def check_wa_window(phone_number: str, session=Depends(require_auth)):
    """Check if the 24h WhatsApp messaging window is open for a customer."""
    phone = phone_number if phone_number.startswith("+") else "+" + phone_number
    try:
        with db._conn() as conn:
            row = conn.execute("""
                SELECT MAX(timestamp) as last_inbound
                FROM customer_conversations
                WHERE phone_number=? AND direction='inbound'
            """, (phone,)).fetchone()
        if row and row["last_inbound"]:
            from datetime import datetime, timedelta
            last = datetime.fromisoformat(row["last_inbound"].replace("Z","").replace(" ","T"))
            window_open = (datetime.utcnow() - last) < timedelta(hours=24)
        else:
            window_open = False
        return {"phone_number": phone, "window_open": window_open,
                "last_inbound": row["last_inbound"] if row else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Contact enrichment endpoint ───────────────────────────────────────────────

class ContactEnrichBody(BaseModel):
    name: str = None
    email: str = None
    company: str = None
    need_category: str = None
    status: str = None


@app.patch("/api/customers/{phone_number}/enrich")
async def enrich_contact(phone_number: str, body: ContactEnrichBody, session=Depends(require_auth)):
    """Update enrichment fields on a customer contact."""
    kwargs = {k: v for k, v in body.dict().items() if v}
    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")
    db.update_contact_enrichment(phone_number, **kwargs)
    return {"ok": True, "phone_number": phone_number, "updated": list(kwargs.keys())}


# ── My permissions (for frontend role-gating) ─────────────────────────────────

@app.get("/api/auth/permissions")
async def my_permissions(session=Depends(require_auth)):
    """Return permissions for the current user."""
    username = session.get("username", "")
    perms = db.get_role_permissions(session.get("role", "support"))
    return {"username": username, "role": session.get("role"), "permissions": perms}
