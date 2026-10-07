"""AI lead qualification for Pakkmaxx CRM.

Flow: trigger (VerzChat message / manual / quiet conversation) -> background job ->
context (VerzChat messages + minimal CRM facts, redacted) -> provider (DeepSeek) ->
validation -> append-only Pakkmaxx AI Qualification record -> AI fields on the lead.
The AI never changes lead status, ownership or human decisions.
"""
