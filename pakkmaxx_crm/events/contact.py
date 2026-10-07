from pakkmaxx_crm.utils import normalize_email, normalize_phone


def validate(doc, method=None):
	"""Store phone numbers and emails in one canonical form so duplicates can be found."""
	for row in doc.get("phone_nos") or []:
		row.phone = normalize_phone(row.phone)
	for row in doc.get("email_ids") or []:
		row.email_id = normalize_email(row.email_id)
	for field in ("mobile_no", "phone", "pkx_whatsapp_no"):
		if doc.get(field):
			doc.set(field, normalize_phone(doc.get(field)))
	if doc.get("email_id"):
		doc.email_id = normalize_email(doc.email_id)
	if not doc.get("pkx_whatsapp_no") and doc.get("mobile_no"):
		doc.pkx_whatsapp_no = doc.mobile_no
