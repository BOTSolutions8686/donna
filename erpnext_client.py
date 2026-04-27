"""
ERPNext API client for Cloud Agent.
"""
import requests
from datetime import date, timedelta
from config import CONFIG


def _headers():
    cfg = CONFIG["erpnext"]
    return {"Authorization": f"token {cfg['api_key']}:{cfg['api_secret']}"}


def _base():
    return CONFIG["erpnext"]["url"]


def get(endpoint, params=None):
    r = requests.get(f"{_base()}{endpoint}", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def post(method, data=None):
    r = requests.post(
        f"{_base()}/api/method/{method}",
        headers=_headers(),
        json=data or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_list(doctype, filters=None, fields=None, limit=20, order_by=None):
    payload = {"doctype": doctype, "limit_page_length": limit}
    if filters:
        payload["filters"] = filters
    if fields:
        payload["fields"] = fields
    if order_by:
        payload["order_by"] = order_by
    result = post("frappe.client.get_list", payload)
    return result.get("message", [])


def get_doc(doctype, name):
    result = get(f"/api/resource/{requests.utils.quote(doctype)}/{requests.utils.quote(str(name))}")
    return result.get("data", {})


def save_doc(doc):
    """Save (insert or update) a document."""
    result = post("frappe.client.save", {"doc": doc})
    return result.get("message", {})


def create_doc(doctype, fields):
    return save_doc({"doctype": doctype, **fields})


# ── Business queries ─────────────────────────────────────────────────────────


def get_overdue_invoices():
    return get_list(
        "Sales Invoice",
        filters=[["status", "in", ["Overdue"]], ["docstatus", "=", 1]],
        fields=["name", "customer", "grand_total", "outstanding_amount", "due_date", "posting_date", "company"],
        limit=100,
        order_by="due_date asc",
    )


def get_unconverted_proformas():
    return get_list(
        "Sales Order",
        filters=[
            ["status", "in", ["To Bill", "To Deliver and Bill"]],
            ["docstatus", "=", 1],
        ],
        fields=["name", "customer", "grand_total", "transaction_date", "delivery_date", "per_billed", "status", "company"],
        limit=100,
        order_by="transaction_date asc",
    )


def get_pricing_context():
    """Fetch recent Quotations and Proforma Invoices for pricing context."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
    quotations = get_list(
        "Quotation",
        filters=[["docstatus", "=", 1], ["transaction_date", ">", since]],
        fields=["name", "party_name", "grand_total", "transaction_date", "valid_till"],
        limit=50,
        order_by="transaction_date desc",
    )
    proformas = get_list(
        "Sales Order",
        filters=[["status", "in", ["To Bill", "To Deliver and Bill"]], ["docstatus", "=", 1]],
        fields=["name", "customer", "grand_total", "transaction_date"],
        limit=50,
        order_by="transaction_date desc",
    )
    return {"quotations": quotations, "proformas": proformas}


def get_zatca_rejections(since_hours=1):
    from datetime import datetime
    since = (datetime.utcnow() - timedelta(hours=since_hours)).strftime("%Y-%m-%d %H:%M:%S")
    return get_list(
        "ZATCA Integration Log",
        filters=[["status", "!=", "Accepted"], ["creation", ">", since]],
        fields=["name", "invoice_reference", "status", "zatca_status", "zatca_http_status_code", "creation"],
        limit=50,
        order_by="creation desc",
    )


def get_gl_snapshot(company=None, days_back=1):
    since = (date.today() - timedelta(days=days_back)).isoformat()
    filters = [["posting_date", ">=", since], ["is_cancelled", "=", 0]]
    if company:
        filters.append(["company", "=", company])
    return get_list(
        "GL Entry",
        filters=filters,
        fields=["name", "account", "debit", "credit", "posting_date",
                "voucher_type", "voucher_no", "party_type", "party", "company", "creation"],
        limit=500,
        order_by="posting_date desc",
    )


def get_purchase_invoices(days_back=90, status=None):
    """Fetch submitted Purchase Invoices."""
    filters = [["docstatus", "=", 1],
               ["posting_date", ">=", (date.today() - timedelta(days=days_back)).isoformat()]]
    if status:
        filters.append(["status", "=", status])
    return get_list(
        "Purchase Invoice",
        filters=filters,
        fields=["name", "supplier", "grand_total", "outstanding_amount",
                "posting_date", "due_date", "status", "bill_no", "company"],
        limit=200,
        order_by="posting_date desc",
    )


def get_overdue_payables():
    """Fetch overdue Purchase Invoices — what we owe and haven't paid."""
    return get_list(
        "Purchase Invoice",
        filters=[["status", "in", ["Overdue"]], ["docstatus", "=", 1]],
        fields=["name", "supplier", "grand_total", "outstanding_amount",
                "due_date", "posting_date", "bill_no", "company"],
        limit=100,
        order_by="due_date asc",
    )


def get_payment_entries(days_back=365):
    """Fetch Payment Entries to analyse customer payment behaviour."""
    since = (date.today() - timedelta(days=days_back)).isoformat()
    return get_list(
        "Payment Entry",
        filters=[["docstatus", "=", 1], ["posting_date", ">=", since], ["payment_type", "=", "Receive"]],
        fields=["name", "party", "paid_amount", "posting_date", "creation", "company"],
        limit=500,
        order_by="posting_date desc",
    )


def get_sales_invoices(days_back=90, status=None):
    filters = [["docstatus", "=", 1],
               ["posting_date", ">=", (date.today() - timedelta(days=days_back)).isoformat()]]
    if status:
        filters.append(["status", "=", status])
    return get_list(
        "Sales Invoice",
        filters=filters,
        fields=["name", "customer", "grand_total", "outstanding_amount",
                "posting_date", "due_date", "status", "company"],
        limit=300,
        order_by="posting_date desc",
    )


def assign_to_user(doctype, name, user, description=""):
    """Assign a document to a user via Frappe's assignment system (_assign)."""
    result = post("frappe.desk.form.assign_to.add", {
        "doctype": doctype,
        "name": name,
        "assign_to": [user],
        "description": description,
        "notify": 1,
    })
    return result.get("message", {})


def get_helpdesk_tickets(status=None, customer=None, priority=None, limit=20):
    """List HD Tickets with optional filters."""
    filters = []
    if status:
        filters.append(["status", "=", status])
    if customer:
        filters.append(["customer", "=", customer])
    if priority:
        filters.append(["priority", "=", priority])
    return get_list(
        "HD Ticket",
        filters=filters if filters else None,
        fields=["name", "subject", "status", "priority", "customer", "raised_by",
                "creation", "modified", "_assign"],
        limit=limit,
        order_by="modified desc",
    )


def get_hd_customers(search=None, limit=20):
    """Search HD Customers (helpdesk customer list, separate from Sales customers)."""
    filters = []
    if search:
        filters.append(["customer_name", "like", f"%{search}%"])
    return get_list(
        "HD Customer",
        filters=filters if filters else None,
        fields=["name", "customer_name", "domain", "custom_contact", "custom_mobile_no"],
        limit=limit,
    )


def get_hd_agents(limit=50):
    """List HD Agents configured in the helpdesk."""
    try:
        agents = get_list(
            "HD Agent",
            fields=["name", "agent_name", "user"],
            limit=limit,
        )
        if agents:
            return agents
    except Exception:
        pass
    # Fallback: list helpdesk team members via User doctype with roles
    try:
        return get_list(
            "Has Role",
            filters=[["role", "in", ["Support Team", "Helpdesk Agent", "HD Agent"]]],
            fields=["parent as user", "role"],
            limit=limit,
        )
    except Exception:
        return []


def create_helpdesk_ticket(subject, description, priority="Medium", customer=None, agent=None, team=None):
    """Create an HD Ticket. Optionally link to an HD Customer and assign to an agent."""
    doc_fields = {
        "subject": subject,
        "description": description,
        "priority": priority,
    }
    if customer:
        doc_fields["customer"] = customer
    if team:
        doc_fields["team"] = team
    result = create_doc("HD Ticket", doc_fields)
    ticket_name = result.get("name")

    # Assign to agent via Frappe assignment system
    if agent and ticket_name:
        try:
            assign_to_user("HD Ticket", ticket_name, agent,
                           description=f"Assigned for: {subject}")
        except Exception as e:
            result["_agent_assignment_error"] = str(e)

    return result


def convert_proforma_to_invoice(so_name):
    """Convert a Sales Order (Proforma Invoice) to a draft Sales Invoice."""
    result = post(
        "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
        {"source_name": so_name},
    )
    draft_si = result.get("message", {})
    if not draft_si:
        raise ValueError(f"make_sales_invoice returned empty for {so_name}")
    saved = save_doc(draft_si)
    return saved


def submit_doc(doctype, name):
    """Submit a saved draft document (set docstatus=1)."""
    result = post("frappe.client.submit", {"doc": {"doctype": doctype, "name": name}})
    return result.get("message", {})


def convert_and_submit_proforma(so_name):
    """Convert a Proforma Invoice (Sales Order) to a Sales Invoice and submit it in one step."""
    result = post(
        "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
        {"source_name": so_name},
    )
    draft_si = result.get("message", {})
    if not draft_si:
        raise ValueError(f"make_sales_invoice returned empty for {so_name}")
    saved = save_doc(draft_si)
    si_name = saved.get("name")
    if not si_name:
        raise ValueError("Sales Invoice was saved but name not returned")
    submitted = submit_doc("Sales Invoice", si_name)
    return submitted


def get_error_logs(since_hours=24, search=None, limit=20):
    """Fetch ERPNext Error Log entries. Optionally filter by keyword in method/error."""
    import json as _json
    from datetime import datetime, timezone
    since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime("%Y-%m-%d %H:%M:%S")
    cfg = CONFIG["erpnext"]
    params = {
        "limit": limit,
        "order_by": "creation desc",
        "filters": _json.dumps([["creation", ">", since]]),
    }
    r = requests.get(
        f"{cfg['url']}/api/resource/Error Log",
        headers=_headers(),
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    names = [row["name"] for row in r.json().get("data", [])]

    logs = []
    for name in names:
        doc_r = requests.get(
            f"{cfg['url']}/api/resource/Error Log/{name}",
            headers=_headers(),
            timeout=30,
        )
        if doc_r.status_code != 200:
            continue
        doc = doc_r.json().get("data", {})
        method = doc.get("method", "")
        error = doc.get("error", "")
        if search and search.lower() not in method.lower() and search.lower() not in error.lower():
            continue
        logs.append({
            "name": name,
            "method": method,
            "error": error,
            "creation": doc.get("creation", ""),
            "seen": doc.get("seen", 0),
        })
    return logs


def get_print_formats(doctype):
    """Return list of available print format names for a doctype."""
    rows = get_list(
        "Print Format",
        filters=[["doc_type", "=", doctype], ["disabled", "=", 0]],
        fields=["name", "doc_type"],
        limit=20,
    )
    return [r["name"] for r in rows]


def get_doc_pdf(doctype, name, print_format=None):
    """Download the PDF of any document. Uses configured default format if none given."""
    cfg = CONFIG["erpnext"]
    if not print_format:
        # Use configured default per doctype, fall back to first available
        defaults = cfg.get("default_print_formats", {})
        print_format = defaults.get(doctype, "")
        if not print_format:
            formats = get_print_formats(doctype)
            print_format = formats[0] if formats else ""
    params = {
        "doctype": doctype,
        "name": name,
        "no_letterhead": 0,
    }
    if print_format:
        params["format"] = print_format
    r = requests.get(
        f"{cfg['url']}/api/method/frappe.utils.print_format.download_pdf",
        headers={"Authorization": f"token {cfg['api_key']}:{cfg['api_secret']}"},
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.content, print_format or "default"


def get_invoice_pdf(si_name, print_format=None):
    """Download the PDF of a Sales Invoice. Returns raw bytes."""
    content, _ = get_doc_pdf("Sales Invoice", si_name, print_format=print_format)
    return content


def get_companies():
    return get_list("Company", fields=["name", "abbr", "country", "default_currency"], limit=20)


def get_profit_and_loss(company, from_date, to_date, periodicity="Monthly"):
    """Fetch P&L Statement from ERPNext. Returns (result_rows, columns)."""
    import requests as _req
    import json as _json
    cfg = CONFIG["erpnext"]
    auth = "token " + cfg["api_key"] + ":" + cfg["api_secret"]
    r = _req.post(
        cfg["url"] + "/api/method/frappe.desk.query_report.run",
        headers={"Authorization": auth},
        data={
            "report_name": "Profit and Loss Statement",
            "filters": _json.dumps({
                "company": company,
                "periodicity": periodicity,
                "period_start_date": from_date,
                "period_end_date": to_date,
                "filter_based_on": "Date Range",
            }),
        },
        timeout=30,
    )
    r.raise_for_status()
    msg = r.json().get("message", {})
    return msg.get("result", []), msg.get("columns", [])


def update_helpdesk_ticket(ticket_name, updates):
    """Update fields on an existing HD Ticket. Fetches first to avoid timestamp conflicts."""
    doc = get_doc("HD Ticket", ticket_name)
    if not doc:
        raise ValueError("Ticket " + str(ticket_name) + " not found")
    doc.update(updates)
    return save_doc(doc)


def add_ticket_comment(ticket_name, content, commenter_name="Donna (AI)"):
    """
    Post a comment/reply on an HD Ticket visible in the ticket thread.
    Uses Frappe's built-in comment API so it appears in the ticket timeline.
    """
    try:
        result = post(
            "frappe.desk.form.utils.add_comment",
            {
                "reference_doctype": "HD Ticket",
                "reference_name": str(ticket_name),
                "content": content,
                "comment_email": CONFIG["erpnext"].get("api_key", "donna@botsolutions.tech"),
                "comment_by": commenter_name,
            },
        )
        return result.get("message", {})
    except Exception:
        # Fallback: insert a Comment document directly
        return create_doc("Comment", {
            "comment_type": "Comment",
            "reference_doctype": "HD Ticket",
            "reference_name": str(ticket_name),
            "content": content,
            "comment_by": commenter_name,
        })


def resolve_ticket(ticket_name):
    """Change HD Ticket status to Resolved."""
    return update_helpdesk_ticket(ticket_name, {"status": "Resolved"})


def close_ticket(ticket_name):
    """Change HD Ticket status to Closed."""
    return update_helpdesk_ticket(ticket_name, {"status": "Closed"})


def get_ticket_with_comments(ticket_name):
    """
    Fetch full HD Ticket doc plus recent comments from the timeline.
    Returns dict with ticket fields and a 'comments' list.
    """
    ticket = get_doc("HD Ticket", ticket_name)
    comments = []
    try:
        raw = get_list(
            "Comment",
            filters=[
                ["reference_doctype", "=", "HD Ticket"],
                ["reference_name", "=", str(ticket_name)],
                ["comment_type", "=", "Comment"],
            ],
            fields=["comment_by", "content", "creation"],
            limit=20,
            order_by="creation desc",
        )
        comments = [{"by": c["comment_by"], "text": c["content"], "at": c["creation"][:16]}
                    for c in raw]
    except Exception:
        pass
    if ticket:
        ticket["_comments"] = comments
    return ticket


def retry_zatca_invoice(invoice_name):
    """
    Attempt to retry ZATCA submission for a Sales Invoice.
    Tries known KSA compliance endpoints; returns status and any error message.
    """
    import json as _json
    cfg = CONFIG["erpnext"]
    auth = "token " + cfg["api_key"] + ":" + cfg["api_secret"]

    # Strategy: try known whitelist endpoints in order
    endpoints = [
        ("ksa_compliance.api.submit_invoice",            {"invoice_name": invoice_name}),
        ("ksa_compliance.zatca.api.submit_invoice",      {"invoice_name": invoice_name}),
        ("lavalon_ksa.api.zatca_submit",                 {"invoice_name": invoice_name}),
        ("erpnext.regional.saudi_arabia.api.zatca_submit", {"invoice_name": invoice_name}),
    ]
    last_error = ""
    for method, payload in endpoints:
        try:
            r = requests.post(
                cfg["url"] + "/api/method/" + method,
                headers={"Authorization": auth},
                json=payload,
                timeout=20,
            )
            if r.status_code in (200, 202):
                return {"success": True, "method": method, "response": r.json()}
            last_error = r.text[:300]
        except Exception as e:
            last_error = str(e)

    return {"success": False, "error": last_error}


def get_low_stock_items(warehouse=None):
    """Return items where actual_qty <= reorder_level (or actual_qty <= 0)."""
    import json as _json
    cfg = CONFIG["erpnext"]
    params = {"limit": 100, "order_by": "actual_qty asc"}
    if warehouse:
        params["filters"] = _json.dumps([["warehouse", "=", warehouse]])
    r = requests.get(
        cfg["url"] + "/api/resource/Bin",
        headers=_headers(),
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    names = [row["name"] for row in r.json().get("data", [])]
    low = []
    for name in names[:50]:  # cap API calls
        doc_r = requests.get(cfg["url"] + "/api/resource/Bin/" + name, headers=_headers(), timeout=15)
        if doc_r.status_code != 200:
            continue
        doc = doc_r.json().get("data", {})
        actual = doc.get("actual_qty", 0) or 0
        reorder = doc.get("reorder_level", 0) or 0
        if actual <= reorder or actual <= 0:
            low.append({
                "item_code": doc.get("item_code", ""),
                "warehouse": doc.get("warehouse", ""),
                "actual_qty": actual,
                "reorder_level": reorder,
                "projected_qty": doc.get("projected_qty", 0),
            })
    return low


def check_instance_health():
    """Check ERPNext reachability, SSL expiry, and recent background job failures."""
    import ssl, socket, json as _json
    from datetime import datetime, timezone
    cfg = CONFIG["erpnext"]
    result = {}

    # 1. Ping
    try:
        r = requests.get(cfg["url"] + "/api/method/frappe.ping", headers=_headers(), timeout=10)
        result["reachable"] = r.status_code == 200 and "pong" in r.text
    except Exception as e:
        result["reachable"] = False
        result["ping_error"] = str(e)

    # 2. SSL expiry
    try:
        hostname = cfg["url"].replace("https://", "").replace("http://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(5)
            s.connect((hostname, 443))
            cert = s.getpeercert()
        expiry_str = cert["notAfter"]
        expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_left = (expiry - datetime.now(timezone.utc)).days
        result["ssl_expiry"] = expiry_str
        result["ssl_days_left"] = days_left
    except Exception as e:
        result["ssl_error"] = str(e)

    # 3. Recent background job failures
    try:
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        r2 = requests.get(
            cfg["url"] + "/api/resource/Scheduled Job Log",
            headers=_headers(),
            params={"limit": 50, "order_by": "creation desc",
                    "filters": _json.dumps([["creation", ">", since]])},
            timeout=15,
        )
        if r2.status_code == 200:
            jobs = r2.json().get("data", [])
            result["bg_jobs_24h"] = len(jobs)
            # Fetch statuses
            failed = []
            for j in jobs[:20]:
                doc_r = requests.get(cfg["url"] + "/api/resource/Scheduled Job Log/" + j["name"],
                                     headers=_headers(), timeout=10)
                if doc_r.status_code == 200:
                    doc = doc_r.json().get("data", {})
                    if doc.get("status") == "Failed":
                        failed.append(doc.get("scheduled_job_type", j["name"]))
            result["failed_bg_jobs"] = failed
    except Exception as e:
        result["bg_jobs_error"] = str(e)

    # 4. Donna server disk
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        result["disk_total_gb"] = round(total / 1e9, 1)
        result["disk_used_gb"] = round(used / 1e9, 1)
        result["disk_free_gb"] = round(free / 1e9, 1)
        result["disk_used_pct"] = round(used / total * 100, 1)
    except Exception as e:
        result["disk_error"] = str(e)

    return result


def send_email(to, subject, message, reference_doctype="", reference_name=""):
    """Send an email via ERPNext Communication doctype."""
    import json as _json
    payload = {
        "recipients": to,
        "subject": subject,
        "content": message,
        "send_email": 1,
        "doctype": reference_doctype or "Communication",
        "name": reference_name or "",
    }
    r = requests.post(
        _base() + "/api/method/frappe.core.doctype.communication.email.make",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("message", {})


# ── Meta Cloud API direct client ─────────────────────────────────────────────
import requests as _meta_requests
import logging as _meta_log

_wa_log = _meta_log.getLogger('donna')


def _meta_headers():
    """Return auth headers for Meta Cloud API."""
    token = CONFIG.get('meta_whatsapp', {}).get('access_token', '')
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def _meta_url(path=''):
    """Build Meta API URL for the configured phone number."""
    cfg = CONFIG.get('meta_whatsapp', {})
    version = cfg.get('api_version', 'v23.0')
    phone_id = cfg.get('phone_number_id', '')
    base = cfg.get('base_url', 'https://graph.facebook.com')
    return f'{base}/{version}/{phone_id}{path}'


def send_whatsapp(to: str, message: str) -> dict:
    """
    Send a free-form WhatsApp message directly via Meta Cloud API.
    Only works within the 24h customer-initiated session window.
    Returns dict with wamid on success.
    """
    to_clean = to.lstrip('+')
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to_clean,
        'type': 'text',
        'text': {'body': message, 'preview_url': False},
    }
    r = _meta_requests.post(
        _meta_url('/messages'),
        headers=_meta_headers(),
        json=payload,
        timeout=15,
    )
    if r.status_code == 200:
        data = r.json()
        wamid = data.get('messages', [{}])[0].get('id', '')
        return {'name': wamid, 'wamid': wamid, 'status': 'sent'}
    else:
        _wa_log.error('Meta WA send failed %s: %s', r.status_code, r.text[:200])
        raise Exception(f'Meta API error {r.status_code}: {r.text[:200]}')


def get_whatsapp_templates(limit: int = 50) -> list:
    """
    Fetch approved WhatsApp templates directly from Meta Business API.
    Returns list of dicts with template_name, status, language.
    """
    cfg = CONFIG.get('meta_whatsapp', {})
    business_id = cfg.get('business_id', '')
    version = cfg.get('api_version', 'v23.0')
    base = cfg.get('base_url', 'https://graph.facebook.com')
    r = _meta_requests.get(
        f'{base}/{version}/{business_id}/message_templates',
        headers=_meta_headers(),
        params={
            'limit': limit,
            'status': 'APPROVED',
            'fields': 'name,status,language,components',
        },
        timeout=15,
    )
    if r.status_code == 200:
        templates = r.json().get('data', [])
        return [
            {
                'template_name': t.get('name', ''),
                'language': t.get('language', 'en'),
                'status': t.get('status', ''),
                'name': t.get('name', ''),
            }
            for t in templates
        ]
    _wa_log.warning('get_whatsapp_templates failed %s: %s', r.status_code, r.text[:100])
    return []


def send_whatsapp_template(to: str, template_name: str,
                           parameters: list = None,
                           language_code: str = 'en') -> dict:
    """
    Send a WhatsApp template message directly via Meta Cloud API.
    Works outside the 24h session window.
    parameters = list of text strings for {{1}}, {{2}}, etc.
    """
    to_clean = to.lstrip('+')
    components = []
    if parameters:
        components.append({
            'type': 'body',
            'parameters': [{'type': 'text', 'text': str(p)} for p in parameters],
        })
    payload = {
        'messaging_product': 'whatsapp',
        'to': to_clean,
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': language_code},
            'components': components,
        },
    }
    r = _meta_requests.post(
        _meta_url('/messages'),
        headers=_meta_headers(),
        json=payload,
        timeout=15,
    )
    if r.status_code == 200:
        data = r.json()
        wamid = data.get('messages', [{}])[0].get('id', '')
        return {'name': wamid, 'wamid': wamid, 'status': 'sent'}
    else:
        _wa_log.error('Meta WA template failed %s: %s', r.status_code, r.text[:200])
        raise Exception(f'Meta template error {r.status_code}: {r.text[:200]}')


def check_delivery_status(wamid: str) -> str:
    """
    Delivery status is now tracked via Meta webhooks (not polling).
    Status is stored in DB via update_delivery_status.
    This function is kept for backward compatibility.
    """
    return None



def get_bank_accounts(company=None):
    """Return bank and cash accounts, optionally filtered by company."""
    filters = [["account_type", "in", ["Bank", "Cash"]], ["is_group", "=", 0]]
    if company:
        filters.append(["company", "=", company])
    return get_list(
        "Account",
        filters=filters,
        fields=["name", "account_type", "company"],
        limit=50,
    )


def create_payment_entry(invoice_name, paid_amount=None, bank_account=None,
                         reference_no="", reference_date=None):
    """
    Create a draft Payment Entry for a received customer payment against a Sales Invoice.
    Uses ERPNext's get_payment_entry helper to pre-fill fields, then saves as draft.
    """
    from datetime import date as _date
    result = post(
        "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
        {"dt": "Sales Invoice", "dn": invoice_name},
    )
    draft = result.get("message", {})
    if not draft:
        raise ValueError(f"Could not build payment entry from {invoice_name}")

    if paid_amount is not None:
        draft["paid_amount"] = paid_amount
        draft["received_amount"] = paid_amount
        for ref in draft.get("references", []):
            ref["allocated_amount"] = paid_amount

    if bank_account:
        draft["paid_to"] = bank_account

    if reference_no:
        draft["reference_no"] = reference_no

    if reference_date:
        draft["reference_date"] = reference_date
    elif not draft.get("reference_date"):
        draft["reference_date"] = _date.today().isoformat()

    return save_doc(draft)


def download_whatsapp_media(media_url):
    """
    Download WhatsApp media file. Handles both local ERPNext paths and external URLs.
    Returns raw bytes.
    """
    cfg = CONFIG["erpnext"]
    if media_url.startswith("/") or media_url.startswith(cfg["url"]):
        # Local ERPNext file — use API auth
        full_url = media_url if media_url.startswith("http") else cfg["url"] + media_url
        r = requests.get(full_url, headers=_headers(), timeout=30)
        r.raise_for_status()
        return r.content
    else:
        # External URL — try without auth first
        r = requests.get(media_url, timeout=30)
        r.raise_for_status()
        return r.content


def load_chart_of_accounts(company=None):
    """Fetch all active accounts from ERPNext Chart of Accounts."""
    filters = [["disabled", "=", 0]]
    if company:
        filters.append(["company", "=", company])
    return get_list(
        "Account",
        filters=filters,
        fields=["name", "account_name", "account_number", "account_type",
                "root_type", "parent_account", "is_group", "company"],
        limit=2000,
        order_by="lft asc",
    )


def get_voucher_gl_entries(voucher_no, company=None):
    """Return all GL Entry rows for a given voucher number."""
    filters = [["voucher_no", "=", voucher_no], ["is_cancelled", "=", 0]]
    if company:
        filters.append(["company", "=", company])
    return get_list(
        "GL Entry",
        filters=filters,
        fields=["name", "account", "debit", "credit", "party_type", "party",
                "cost_center", "voucher_type", "voucher_no", "posting_date",
                "remarks", "company"],
        limit=50,
    )


def get_trial_balance(company, from_date, to_date):
    """Fetch Trial Balance report from ERPNext. Returns (rows, columns)."""
    import requests as _req
    import json as _json
    cfg = CONFIG["erpnext"]
    auth = "token " + cfg["api_key"] + ":" + cfg["api_secret"]
    # Fiscal year name = the year of to_date (BOT Solutions uses calendar-year fiscal years)
    fiscal_year = str(to_date)[:4]
    r = _req.post(
        cfg["url"] + "/api/method/frappe.desk.query_report.run",
        headers={"Authorization": auth},
        data={
            "report_name": "Trial Balance",
            "filters": _json.dumps({
                "company": company,
                "from_date": from_date,
                "to_date": to_date,
                "fiscal_year": fiscal_year,
                "show_zero_values": 0,
            }),
        },
        timeout=30,
    )
    r.raise_for_status()
    msg = r.json().get("message", {})
    return msg.get("result", []), msg.get("columns", [])


def create_journal_entry(accounts, posting_date, voucher_type="Journal Entry",
                         user_remark="", company=None):
    """
    Create a Journal Entry in ERPNext (saved as draft).
    accounts = list of dicts with keys:
      account, debit_in_account_currency, credit_in_account_currency,
      party_type (optional), party (optional), cost_center (optional)
    """
    doc = {
        "doctype": "Journal Entry",
        "voucher_type": voucher_type,
        "posting_date": posting_date,
        "user_remark": user_remark,
        "accounts": [],
    }
    if company:
        doc["company"] = company
    for acc in accounts:
        row = {
            "account": acc["account"],
            "debit_in_account_currency": float(acc.get("debit_in_account_currency") or 0),
            "credit_in_account_currency": float(acc.get("credit_in_account_currency") or 0),
        }
        for opt_field in ("party_type", "party", "cost_center"):
            if acc.get(opt_field):
                row[opt_field] = acc[opt_field]
        doc["accounts"].append(row)
    return save_doc(doc)


def get_balance_sheet(company, from_date, to_date, periodicity="Yearly"):
    """Fetch Balance Sheet from ERPNext. Returns (result_rows, columns)."""
    import requests as _req
    import json as _json
    cfg = CONFIG["erpnext"]
    auth = "token " + cfg["api_key"] + ":" + cfg["api_secret"]
    r = _req.post(
        cfg["url"] + "/api/method/frappe.desk.query_report.run",
        headers={"Authorization": auth},
        data={
            "report_name": "Balance Sheet",
            "filters": _json.dumps({
                "company": company,
                "periodicity": periodicity,
                "period_start_date": from_date,
                "period_end_date": to_date,
                "filter_based_on": "Date Range",
            }),
        },
        timeout=30,
    )
    r.raise_for_status()
    msg = r.json().get("message", {})
    return msg.get("result", []), msg.get("columns", [])
