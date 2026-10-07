"""Live HTTP permission & API smoke test, run against a running site (dev or staging).

Usage:
    PKX_BASE=http://127.0.0.1:8000 PKX_HOST=pakkmaxx-crm.localhost PKX_PASSWORD=... \
        python3 scripts/http_smoke_test.py

Needs the demo users (kwame, akua, teamlead, manager, viewer @pakkmaxx.local) created with
scripts/create_demo_users.py. Never run against production data.
"""

import json
import os
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = os.environ.get("PKX_BASE", "http://127.0.0.1:8000")
HOST = os.environ.get("PKX_HOST", "pakkmaxx-crm.localhost")
PW = os.environ["PKX_PASSWORD"]
results = []


class Client:
	def __init__(self, user=None):
		self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
		self.csrf = None
		if user:
			status, body = self.req("POST", "/api/method/login", {"usr": user, "pwd": PW})
			assert status == 200, (user, status, body)
			# CSRF token for POSTs from a session
			status, html = self.req("GET", "/app", raw=True)
			marker = 'csrf_token = "'
			if marker in html:
				self.csrf = html.split(marker, 1)[1].split('"', 1)[0]

	def req(self, method, path, data=None, raw=False):
		headers = {"Host": HOST, "Accept": "application/json"}
		body = None
		if data is not None:
			body = json.dumps(data).encode()
			headers["Content-Type"] = "application/json"
		if self.csrf:
			headers["X-Frappe-CSRF-Token"] = self.csrf
		request = urllib.request.Request(BASE + path.replace(" ", "%20"), data=body, method=method, headers=headers)
		try:
			with self.opener.open(request) as r:
				text = r.read().decode()
				return r.status, text if raw else json.loads(text or "{}")
		except urllib.error.HTTPError as e:
			text = e.read().decode()
			try:
				return e.code, json.loads(text)
			except Exception:
				return e.code, text


def check(name, ok, detail=""):
	results.append((name, ok))
	print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if not ok and detail else ""))


def mobile():
	return f"02{random.choice([4, 5])}{random.randint(1000000, 9999999)}"


kwame, akua = Client("kwame@pakkmaxx.local"), Client("akua@pakkmaxx.local")
teamlead, manager, viewer = Client("teamlead@pakkmaxx.local"), Client("manager@pakkmaxx.local"), Client("viewer@pakkmaxx.local")
anon = Client()

# Kwame creates a WhatsApp lead through REST
status, body = kwame.req("POST", "/api/resource/CRM Lead", {"first_name": "Efua", "last_name": "Boateng",
	"mobile_no": mobile(), "source": "WhatsApp", "lead_owner": "kwame@pakkmaxx.local"})
check("rep creates lead via REST", status == 200, f"{status} {str(body)[:200]}")
lead = body.get("data", {}).get("name")
check("phone normalised to +233", body.get("data", {}).get("mobile_no", "").startswith("+233"))

status, body = kwame.req("POST", "/api/method/pakkmaxx_crm.api.activities.log_interaction",
	{"reference_doctype": "CRM Lead", "reference_name": lead, "summary": "Wants sea freight for 3 CBM shoes"})
check("rep logs WhatsApp chat via API", status == 200, f"{status} {str(body)[:200]}")
status, body = kwame.req("GET", f"/api/resource/CRM Lead/{urllib.parse.quote(lead)}")
check("first contact moved lead to Contacted", body.get("data", {}).get("status") == "Contacted", str(body)[:200])

# Other rep and anonymous access
status, body = akua.req("GET", f"/api/resource/CRM Lead/{urllib.parse.quote(lead)}")
check("other rep gets 403 on lead via REST", status == 403, str(status))
status, body = akua.req("GET", "/api/resource/CRM Lead?limit_page_length=500&fields=[\"name\"]")
check("other rep's lead list excludes it", status == 200 and lead not in [r["name"] for r in body.get("data", [])])
status, body = akua.req("GET", f"/api/resource/FCRM Note?filters={urllib.parse.quote(json.dumps({'reference_docname': lead}))}")
check("other rep cannot list the lead's notes", status == 200 and not body.get("data"), str(body)[:200])
status, body = akua.req("GET", f"/api/method/pakkmaxx_crm.api.activities.get_timeline?reference_doctype=CRM%20Lead&reference_name={urllib.parse.quote(lead)}")
check("other rep gets 403 on timeline API", status == 403, str(status))
status, body = akua.req("PUT", f"/api/resource/CRM Lead/{urllib.parse.quote(lead)}", {"lead_owner": "akua@pakkmaxx.local"})
check("other rep cannot take the lead", status == 403, str(status))
status, body = anon.req("GET", "/api/resource/CRM Lead")
check("anonymous gets 403 on leads", status == 403, str(status))
status, body = anon.req("POST", "/api/method/pakkmaxx_crm.api.leads.capture_lead", {"first_name": "Spam", "mobile_no": mobile()})
check("anonymous cannot call capture_lead", status == 403, str(status))

# Rep tampering
status, body = kwame.req("PUT", f"/api/resource/CRM Lead/{urllib.parse.quote(lead)}", {"lead_owner": "akua@pakkmaxx.local"})
check("rep cannot hand lead to another rep", status == 403, str(status))
status, body = kwame.req("PUT", f"/api/resource/CRM Lead/{urllib.parse.quote(lead)}", {"lead_score": 100, "status": "Negotiation"})
check("rep cannot skip workflow stages", status in (403, 417), str(status))
status, body = kwame.req("PUT", "/api/resource/CRM Deal Status/Won", {"probability": 10})
check("rep cannot edit pipeline", status == 403, str(status))
status, body = kwame.req("PUT", "/api/resource/User/kwame@pakkmaxx.local", {"roles": [{"role": "System Manager"}]})
status2, me = kwame.req("GET", "/api/method/frappe.auth.get_logged_user")
_, roles = manager.req("GET", "/api/method/frappe.core.doctype.user.user.get_roles?arg=kwame@pakkmaxx.local")
check("rep cannot grant themselves System Manager", "System Manager" not in json.dumps(roles), str(roles)[:200])

# Team manager / CRM manager / read only
status, body = teamlead.req("GET", f"/api/resource/CRM Lead/{urllib.parse.quote(lead)}")
check("team lead sees team member's lead", status == 200, str(status))
status, body = manager.req("GET", f"/api/resource/CRM Lead/{urllib.parse.quote(lead)}")
check("CRM manager sees any lead", status == 200, str(status))
status, body = viewer.req("PUT", f"/api/resource/CRM Lead/{urllib.parse.quote(lead)}", {"pkx_next_action": "x"})
check("read-only user cannot edit", status == 403, str(status))
status, body = viewer.req("POST", "/api/resource/CRM Lead", {"first_name": "Nope", "mobile_no": mobile()})
check("read-only user cannot create", status == 403, str(status))

# Dashboard / report / UI pages
status, body = kwame.req("GET", "/api/method/pakkmaxx_crm.api.dashboard.summary")
check("dashboard summary API", status == 200 and "leads" in body.get("message", {}), str(status))
status, body = manager.req("POST", "/api/method/frappe.desk.query_report.run",
	{"report_name": "Pakkmaxx Lead Source Attribution", "filters": {}})
check("attribution report over HTTP", status == 200, str(status))
for path in ("/crm", "/app/pakkmaxx-crm", "/app/crm-lead", "/app/pakkmaxx-customer"):
	status, html = manager.req("GET", path, raw=True)
	check(f"page {path} loads", status == 200, str(status))

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
