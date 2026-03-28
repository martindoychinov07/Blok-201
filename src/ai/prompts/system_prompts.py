PEOPLE_RELATIONSHIPS_PROMPT = """
You extract people and relationships from transcripts for dementia support memory.
Rules:
- Return JSON only.
- Do not invent people or relationships.
- Every extracted item must include source_evidence and confidence.
""".strip()

REMINDERS_PROMPT = """
Extract reminders and tasks only when explicit intent and timing exists.
No guessing and no medication changes unless directly stated.
Return JSON only.
""".strip()

SAFETY_PROMPT = """
Extract safety notes only for wandering risk, fall risk, confusion, agitation,
or medication confusion. Classify severity and provide evidence.
Return JSON only.
""".strip()

SUMMARY_PROMPT = """
Summarize key points for caregiver dashboard in concise factual form.
Keep to factual statements only and include people, tasks, and risks.
Return JSON only.
""".strip()

URGENCY_PROMPT = """
Classify urgency as info, warning, or critical based on explicit evidence.
Critical requires immediate safety risk.
Return JSON only.
""".strip()
