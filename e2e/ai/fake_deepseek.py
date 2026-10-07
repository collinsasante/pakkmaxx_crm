"""Local stand-in for DeepSeek's /chat/completions (same request/response format) for pipeline tests.
Records every request; replies with a canned assessment chosen from the conversation content.
Write 'garbage' to ./mode to make it return invalid JSON."""
import json, os, time
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "requests.jsonl")

def assessment(user):
    if "100 cartons" in user:
        return {"classification": "high_value", "score": 88, "confidence": 0.9, "intent": "shipping_service", "service_interest": ["sea_freight"], "product_category": "clothes", "origin": "Guangzhou", "destination": "Accra", "quantity": "about 100 cartons monthly", "estimated_volume": None, "expected_shipping_date": None, "estimated_value": None, "buying_signals": ["Recurring monthly shipments", "Large volume"], "negative_signals": [], "missing_information": ["Next shipment date"], "recommended_next_action": "Arrange a call to discuss a long-term rate.", "summary": "Monthly importer of ~100 cartons looking for a new forwarder.", "evidence": ["customer: 'about 100 cartons'"], "context_summary": "Monthly clothes importer, ~100 cartons."}
    if "20 cartons" in user:
        return {"classification": "qualified", "score": 74, "confidence": 0.86, "intent": "shipping_service", "service_interest": ["sea_freight"], "product_category": "shoes", "origin": "Guangzhou, China", "destination": "Ghana", "quantity": "about 20 cartons", "estimated_volume": None, "expected_shipping_date": "next week" if "next week" in user else None, "estimated_value": None, "buying_signals": ["Specific shipment", "Quantity given", "Asked for sea freight price"], "negative_signals": [], "missing_information": ["Carton dimensions", "Weight"], "recommended_next_action": "Ask for carton dimensions and weight, then prepare a sea freight quotation.", "summary": "Customer wants to ship ~20 cartons of shoes from Guangzhou to Ghana.", "evidence": ["customer: 'about 20 cartons in Guangzhou'"], "context_summary": "Shoes, ~20 cartons in Guangzhou, sea freight."}
    return {"classification": "needs_follow_up", "score": 45, "confidence": 0.5, "intent": "general_enquiry", "service_interest": [], "product_category": None, "origin": None, "destination": None, "quantity": None, "estimated_volume": None, "expected_shipping_date": None, "estimated_value": None, "buying_signals": [], "negative_signals": [], "missing_information": ["What they ship", "Quantity"], "recommended_next_action": "Ask what they want to ship and how much.", "summary": "General enquiry.", "evidence": [], "context_summary": "General enquiry."}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with open(LOG, "a") as f:
            f.write(json.dumps({"path": self.path, "auth": self.headers.get("Authorization"), "body": body}) + "\n")
        user = body["messages"][1]["content"]
        mode = open(os.path.join(HERE, "mode")).read().strip() if os.path.exists(os.path.join(HERE, "mode")) else ""
        content = "{not valid json" if mode == "garbage" else json.dumps(assessment(user))
        resp = {"id": "x", "object": "chat.completion", "created": int(time.time()), "model": body["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": len(user) // 4, "completion_tokens": 250, "total_tokens": len(user) // 4 + 250}}
        raw = json.dumps(resp).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

HTTPServer(("127.0.0.1", 8765), H).serve_forever()
