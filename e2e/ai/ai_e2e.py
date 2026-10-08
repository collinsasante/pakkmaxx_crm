"""Live AI pipeline test: real VerzChat -> webhook -> verzchat_crm hook -> AI trigger -> background job ->
messages from VerzChat API -> DeepSeekProvider HTTP (local DeepSeek-format stand-in) -> validation -> lead."""

import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("CRM_URL", "http://127.0.0.1:8000")
from e2e_flow import Frappe, check, customer_says, results, wait_for  # noqa: E402

BENCH = os.path.expanduser("~/pakkmaxx-crm/frappe-bench")
SITE = "pakkmaxx-crm.localhost"


def site_py(code: str):
	return subprocess.run([f"{BENCH}/env/bin/python", "-c", f"import frappe; frappe.init(site='{SITE}', sites_path='.'); frappe.connect()\n{code}"],
		cwd=f"{BENCH}/sites", capture_output=True, text=True).stdout.strip()


def set_ai(**values):
	site_py(f"s = frappe.get_single('Pakkmaxx CRM Settings'); s.update({values!r}); s.save(); frappe.db.commit()")


def records(manager, lead):
	_s, r = manager.req("GET", f'/api/resource/Pakkmaxx AI Qualification?filters={json.dumps([["lead", "=", lead]])}'
		'&fields=["name","status","trigger","classification","score","messages_analyzed","error","expected_shipping_date"]&order_by=creation%20asc&limit_page_length=50'.replace(" ", "%20"))
	return r.get("data") or []


def lead_ai(manager, lead):
	return manager.req("GET", f"/api/resource/CRM Lead/{lead}")[1]["data"]


def main():
	manager, rep_b = Frappe("manager@pg.test"), Frappe("rep@pg.test")
	phone = f"23324{random.randint(1000000, 9999999)}"

	print("\n== Scenario: new WhatsApp customer, shoes from China")
	customer_says(phone, "Abena Owusu", "Hi, I want to ship shoes from China to Ghana.")
	lead = wait_for(lambda: (manager.lead_by_phone(phone) or [{}])[0].get("name"))
	check("lead created from VerzChat", lead)
	time.sleep(3)
	check("no AI analysis after a single message", not records(manager, lead))
	customer_says(phone, "Abena Owusu", "I have about 20 cartons in Guangzhou.")
	first = wait_for(lambda: [r for r in records(manager, lead) if r["status"] in ("Completed", "Failed")], timeout=60)
	check("AI analysis queued and completed in the background", first and first[0]["status"] == "Completed", first)
	check("triggered by intent keywords after 2 customer messages", first and first[0]["trigger"] == "Intent Keywords", first)
	d = lead_ai(manager, lead)
	check("lead shows AI classification Qualified", d["pkx_ai_classification"] == "Qualified" and d["pkx_ai_score"] == 74, (d["pkx_ai_classification"], d["pkx_ai_score"]))
	check("lead shows missing info and next action", "Carton dimensions" in (d["pkx_ai_missing_information"] or "") and "quotation" in (d["pkx_ai_next_action"] or ""))
	check("lead status untouched by AI", d["status"] == "New", d["status"])

	customer_says(phone, "Abena Owusu", "I want them next week. You can call me on 024 123 4567")
	customer_says(phone, "Abena Owusu", "How much will sea shipping cost?")
	time.sleep(5)
	check("cooldown: no second analysis seconds later", len(records(manager, lead)) == 1, len(records(manager, lead)))
	set_ai(ai_quiet_minutes=0, ai_cooldown_minutes=0)
	site_py("from pakkmaxx_crm.ai.triggers import analyze_quiet_conversations; analyze_quiet_conversations()")
	second = wait_for(lambda: [r for r in records(manager, lead) if r["trigger"] == "Quiet Conversation" and r["status"] == "Completed"], timeout=60)
	check("quiet-conversation trigger analyses the full conversation", second and second[0]["messages_analyzed"] == 4 and second[0]["expected_shipping_date"] == "next week", second)
	set_ai(ai_quiet_minutes=30, ai_cooldown_minutes=10)

	print("\n== What was sent to the AI provider")
	reqs = [json.loads(l) for l in open("ai/requests.jsonl")]
	last = reqs[-1]
	user_payload = "\n".join(r["body"]["messages"][1]["content"] for r in reqs)
	check("server-side key in Authorization header", last["auth"] == "Bearer local-test-key")
	check("JSON output mode + configured model", last["body"]["response_format"] == {"type": "json_object"} and last["body"]["model"] == "deepseek-flash")
	check("customer phone number redacted", "024 123 4567" not in user_payload and "[phone]" in user_payload)
	check("customer name / CRM identifiers not sent", "Abena" not in user_payload and phone not in user_payload and lead not in user_payload)
	check("system prompt marks customer messages untrusted", "UNTRUSTED" in last["body"]["messages"][0]["content"])

	print("\n== Human override")
	s, _ = manager.req("PUT", f"/api/resource/CRM Lead/{lead}", {"pkx_ai_human_classification": "High Value"})
	check("override without reason refused", s != 200, s)
	s, _ = manager.req("PUT", f"/api/resource/CRM Lead/{lead}", {"pkx_ai_human_classification": "High Value", "pkx_ai_override_reason": "Confirmed a 3-container order by phone"})
	d = lead_ai(manager, lead)
	check("override stored and stamped", s == 200 and d["pkx_ai_overridden_by"] == "manager@pg.test" and d["pkx_ai_effective_classification"] == "High Value", (s, d.get("pkx_ai_overridden_by")))
	before = len([r for r in records(manager, lead) if r["status"] == "Completed"])
	s, r = manager.method("pakkmaxx_crm.ai.api.analyze_lead", lead=lead, reanalyze=1)
	third = wait_for(lambda: len([r for r in records(manager, lead) if r["status"] == "Completed"]) > before, timeout=60)
	d = lead_ai(manager, lead)
	check("Re-analyse adds a new history record", third and r["message"]["queued"], r)
	check("AI result updates but human decision is kept", d["pkx_ai_classification"] == "Qualified" and d["pkx_ai_human_classification"] == "High Value" and d["pkx_ai_effective_classification"] == "High Value")

	print("\n== Failures and access")
	open("ai/mode", "w").write("garbage")
	manager.method("pakkmaxx_crm.ai.api.analyze_lead", lead=lead, reanalyze=1)
	failed = wait_for(lambda: [r for r in records(manager, lead) if r["status"] == "Failed"], timeout=60)
	os.remove("ai/mode")
	d = lead_ai(manager, lead)
	check("invalid AI output -> analysis Failed with reason", failed and "Invalid AI response" in failed[0]["error"], failed)
	check("lead keeps its last good AI result", d["pkx_ai_classification"] == "Qualified" and d["pkx_ai_score"] == 74)
	s, _ = rep_b.method("pakkmaxx_crm.ai.api.analyze_lead", lead=lead)
	check("user without access to the lead cannot run AI", s == 403, s)

	set_ai(ai_enabled=0)
	n = len(records(manager, lead))
	customer_says(phone, "Abena Owusu", "Hello? How much for 20 cartons by air?")
	customer_says(phone, "Abena Owusu", "Please reply, I need the price today")
	customer_says(phone, "Abena Owusu", "price?")
	time.sleep(6)
	s, r = manager.method("pakkmaxx_crm.ai.api.analyze_lead", lead=lead)
	check("AI off: no analyses queued, manual request explains it is off", len(records(manager, lead)) == n and r["message"]["queued"] is False, r)
	set_ai(ai_enabled=1)

	print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
	return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
	sys.exit(main())
