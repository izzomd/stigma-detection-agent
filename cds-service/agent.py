import os, json, re

USE_MOCK = not os.environ.get("ANTHROPIC_API_KEY")

# ── Mock detection (keyword-based, same output format as real Claude call) ────

MOCK_PATTERNS = [
    {
        "pattern": r"\bknown alcoholic\b",
        "category": "identity_labels",
        "confidence": 0.97,
        "reason": "Labels the patient by their condition rather than using person-first language; 'known alcoholic' reduces the patient to their disorder and implies a character trait rather than a medical diagnosis.",
        "suggested_rewrite": "patient with known alcohol use disorder"
    },
    {
        "pattern": r"\balcoholic\b",
        "category": "identity_labels",
        "confidence": 0.95,
        "reason": "'Alcoholic' is an identity label that defines the patient by their disorder. DSM-5 terminology is 'alcohol use disorder'.",
        "suggested_rewrite": "patient with alcohol use disorder"
    },
    {
        "pattern": r"\baddict\b",
        "category": "identity_labels",
        "confidence": 0.96,
        "reason": "'Addict' is a stigmatizing identity label. Person-first language and DSM-5 diagnostic terminology should be used instead.",
        "suggested_rewrite": "person with substance use disorder"
    },
    {
        "pattern": r"\bshe claims\b|\bhe claims\b|\bpatient claims\b",
        "category": "distrust_language",
        "confidence": 0.88,
        "reason": "'Claims' signals skepticism toward the patient's self-report without clinical justification, implying the account may be unreliable or dishonest.",
        "suggested_rewrite": "patient reports"
    },
    {
        "pattern": r"\bunreliable historian\b",
        "category": "distrust_language",
        "confidence": 0.91,
        "reason": "Labels the patient as an untrustworthy source of their own history. If history is limited, note the specific reason (e.g., altered mental status) rather than attributing it to the patient's character.",
        "suggested_rewrite": "history limited by acute distress and withdrawal symptoms"
    },
    {
        "pattern": r"\bnon.compli\w+\b",
        "category": "behavioral_framing",
        "confidence": 0.72,
        "reason": "'Non-compliant' frames a complex disease process and its social context as a patient choice or failure. The note already documents the psychosocial drivers.",
        "suggested_rewrite": "medication routine was disrupted in the context of active alcohol use disorder"
    },
    {
        "pattern": r"\bdirty\b",
        "category": "moral_judgment",
        "confidence": 0.98,
        "reason": "'Dirty' applied to a urine drug screen carries strong moral connotations of contamination or wrongdoing. Clinical documentation should use neutral terminology.",
        "suggested_rewrite": "urine drug screen positive for"
    },
    {
        "pattern": r"\brefused\b.*\btreatment\b|\brefuses\b.*\btreatment\b",
        "category": "context_dependent_refusal",
        "confidence": 0.61,
        "reason": "Documenting refusal without noting potential barriers (fear, prior negative experiences, withdrawal symptoms) can make the patient appear difficult rather than contextualizing their decision.",
        "suggested_rewrite": "declined treatment at this time; barriers explored"
    },
    {
        "pattern": r"\bsubstance abuse\b|\balcohol abuse\b|\bdrug abuse\b",
        "category": "clinical_diagnostic",
        "confidence": 0.93,
        "reason": "'Abuse' is outdated DSM-IV terminology with moral connotations. DSM-5 uses 'use disorder' to reflect the clinical reality of addiction as a chronic disease.",
        "suggested_rewrite": "substance use disorder / alcohol use disorder"
    },
    {
        "pattern": r"\bself.neglect\b",
        "category": "behavioral_framing",
        "confidence": 0.82,
        "reason": "'Self-neglect' frames the patient's inability to maintain self-care as a personal failing rather than a consequence of untreated illness, bereavement, and social isolation — all documented in this note.",
        "suggested_rewrite": "self-care routines became unsustainable in the context of bereavement, social isolation, and untreated alcohol use disorder"
    },
    {
        "pattern": r"\btypical of this population\b|\bprior pattern\b.*\bknown\b",
        "category": "moral_judgment",
        "confidence": 0.78,
        "reason": "Characterizing a patient's presentation as typical of their demographic group implies predictability based on identity rather than clinical assessment of the individual.",
        "suggested_rewrite": "consistent with prior withdrawal presentations"
    },
]


def mock_detect(note_text: str) -> list[dict]:
    flags = []
    seen_spans = set()
    text_lower = note_text.lower()

    for rule in MOCK_PATTERNS:
        for match in re.finditer(rule["pattern"], text_lower):
            span = note_text[match.start():match.end()]
            if span.lower() in seen_spans:
                continue
            seen_spans.add(span.lower())
            flags.append({
                "flagged_span": span,
                "category": rule["category"],
                "confidence": rule["confidence"],
                "reason": rule["reason"],
                "suggested_rewrite": rule["suggested_rewrite"],
            })

    flags.sort(key=lambda f: f["confidence"], reverse=True)
    return flags


# ── Real Claude detection (used when ANTHROPIC_API_KEY is set) ────────────────

def claude_detect(note_text: str, patient_id: str = None) -> list[dict]:
    import anthropic
    from prompt import SYSTEM_PROMPT

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Analyze the following clinical note for stigmatizing language.\n\nPatient ID: {patient_id or 'unknown'}\n\n---\n\n{note_text}"
        }]
    )

    raw = message.content[0].text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)

    try:
        return json.loads(raw).get("flags", [])
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group()).get("flags", []) if m else []


# ── Public interface ──────────────────────────────────────────────────────────

def detect_stigma(note_text: str, patient_id: str = None) -> list[dict]:
    if USE_MOCK:
        print("[agent] Using mock detection (no ANTHROPIC_API_KEY set)")
        return mock_detect(note_text)
    return claude_detect(note_text, patient_id)
