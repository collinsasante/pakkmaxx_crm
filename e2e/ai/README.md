# Live AI pipeline test

`ai_e2e.py` runs the whole AI path against a **running local VerzChat** and this Frappe site:
customer WhatsApp messages (signed Meta webhook) → VerzChat → webhook → verzchat_crm handler →
AI trigger → background job → messages read from VerzChat → `DeepSeekProvider` HTTP call → validation →
lead. `fake_deepseek.py` stands in for DeepSeek's `/chat/completions` (same format) so no credits are
spent and every request can be inspected (redaction, auth header, JSON mode).

Point the site at it (`ai_base_url = http://127.0.0.1:8765`), run it, then:
`python3 ai_e2e.py` from a working directory that also contains verzchat_crm's `e2e/` helpers
(`e2e_flow.py`, `vz.py`) and their data files. To judge the real model, run
`bench --site <site> execute pakkmaxx_crm.ai.evaluate.run` with a DeepSeek key configured.
