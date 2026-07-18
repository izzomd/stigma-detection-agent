import os, json, re, requests
from datetime import date

USE_MOCK = not os.environ.get("ANTHROPIC_API_KEY")

# ── FHIR tools Claude can call ────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_patient_info",
        "description": "Retrieve demographic information for a patient (name, age, gender) from the FHIR server.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR patient ID"}
            },
            "required": ["patient_id"]
        }
    },
    {
        "name": "get_patient_conditions",
        "description": "Retrieve active medical conditions and diagnoses for a patient from the FHIR server. Use this to understand the patient's clinical context before reviewing their note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR patient ID"}
            },
            "required": ["patient_id"]
        }
    },
    {
        "name": "get_prior_notes",
        "description": "Retrieve recent clinical documentation titles for a patient to understand prior documentation patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR patient ID"},
                "count": {"type": "integer", "description": "Number of recent notes to retrieve (default 5)"}
            },
            "required": ["patient_id"]
        }
    }
]


def _execute_tool(name: str, inputs: dict, fhir_base: str) -> dict:
    patient_id = inputs.get("patient_id", "")
    try:
        if name == "get_patient_info":
            r = requests.get(f"{fhir_base}/Patient/{patient_id}", timeout=5)
            data = r.json()
            name_obj = (data.get("name") or [{}])[0]
            full_name = " ".join(filter(None, [
                " ".join(name_obj.get("given", [])),
                name_obj.get("family", "")
            ]))
            dob = data.get("birthDate", "")
            age = None
            if dob:
                birth = date.fromisoformat(dob)
                age = (date.today() - birth).days // 365
            return {"name": full_name, "age": age, "gender": data.get("gender", ""), "dob": dob}

        elif name == "get_patient_conditions":
            r = requests.get(
                f"{fhir_base}/Condition?patient={patient_id}&clinical-status=active&_count=20",
                timeout=5
            )
            data = r.json()
            conditions = []
            for entry in data.get("entry", []):
                c = entry["resource"]
                codings = c.get("code", {}).get("coding", [{}])
                display = c.get("code", {}).get("text") or codings[0].get("display", "")
                code = codings[0].get("code", "") if codings else ""
                if display:
                    conditions.append({"display": display, "code": code})
            return {"conditions": conditions}

        elif name == "get_prior_notes":
            count = inputs.get("count", 5)
            r = requests.get(
                f"{fhir_base}/DocumentReference?subject={patient_id}&_count={count}&_sort=-date",
                timeout=5
            )
            data = r.json()
            notes = []
            for entry in data.get("entry", []):
                doc = entry["resource"]
                title = doc.get("description") or doc.get("type", {}).get("text", "Clinical Note")
                note_date = (doc.get("date", "") or "")[:10]
                notes.append({"title": title, "date": note_date})
            return {"notes": notes}

    except Exception as e:
        return {"error": str(e)}

    return {"error": f"Unknown tool: {name}"}


def _summarize_tool_result(name: str, result: dict) -> str:
    if name == "get_patient_info":
        parts = [p for p in [result.get("name"), result.get("age") and f"{result['age']}yo", (result.get("gender") or "").capitalize()] if p]
        return ", ".join(parts) if parts else "Patient found"

    elif name == "get_patient_conditions":
        conditions = result.get("conditions", [])
        if not conditions:
            return "No active conditions on record"
        displays = [c["display"] for c in conditions[:3]]
        suffix = f" +{len(conditions)-3} more" if len(conditions) > 3 else ""
        return "; ".join(displays) + suffix

    elif name == "get_prior_notes":
        notes = result.get("notes", [])
        if not notes:
            return "No prior notes found"
        return f"{len(notes)} prior note{'s' if len(notes) != 1 else ''} found"

    return "Done"


def _tool_label(name: str) -> str:
    return {
        "get_patient_info": "Retrieving patient demographics",
        "get_patient_conditions": "Querying active conditions",
        "get_prior_notes": "Loading prior documentation",
    }.get(name, name)


def _parse_flags(raw: str) -> list[dict]:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    else:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            raw = m.group()

    # Fix: Claude sometimes writes "option A" or "option B" in string values
    raw = re.sub(r'("(?:[^"\\]|\\.)*")\s+or\s+"(?:[^"\\]|\\.)*"', r'\1', raw)

    try:
        return json.loads(raw).get("flags", [])
    except json.JSONDecodeError:
        return []


# ── Mock detection ────────────────────────────────────────────────────────────

MOCK_PATTERNS = [
    {
        "pattern": r"\bknown alcoholic\b",
        "category": "identity_labels",
        "confidence": 0.97,
        "reason": "Labels the patient by their condition rather than using person-first language.",
        "suggested_rewrite": "patient with known alcohol use disorder"
    },
    {
        "pattern": r"\balcoholic\b",
        "category": "identity_labels",
        "confidence": 0.95,
        "reason": "'Alcoholic' is an identity label. DSM-5 terminology is 'alcohol use disorder'.",
        "suggested_rewrite": "patient with alcohol use disorder"
    },
    {
        "pattern": r"\baddict\b",
        "category": "identity_labels",
        "confidence": 0.96,
        "reason": "'Addict' is a stigmatizing identity label.",
        "suggested_rewrite": "person with substance use disorder"
    },
    {
        "pattern": r"\bshe claims\b|\bhe claims\b|\bpatient claims\b",
        "category": "distrust_language",
        "confidence": 0.88,
        "reason": "'Claims' signals skepticism toward the patient's self-report.",
        "suggested_rewrite": "patient reports"
    },
    {
        "pattern": r"\bunreliable historian\b",
        "category": "distrust_language",
        "confidence": 0.91,
        "reason": "Labels the patient as an untrustworthy source of their own history.",
        "suggested_rewrite": "history limited by acute distress and withdrawal symptoms"
    },
    {
        "pattern": r"\bnon.compli\w+\b",
        "category": "behavioral_framing",
        "confidence": 0.72,
        "reason": "'Non-compliant' frames a complex disease process as a patient choice.",
        "suggested_rewrite": "medication routine was disrupted in the context of active alcohol use disorder"
    },
    {
        "pattern": r"\bdirty\b",
        "category": "moral_judgment",
        "confidence": 0.98,
        "reason": "'Dirty' applied to a urine drug screen carries strong moral connotations.",
        "suggested_rewrite": "urine drug screen positive for"
    },
    {
        "pattern": r"\bsubstance abuse\b|\balcohol abuse\b|\bdrug abuse\b",
        "category": "clinical_diagnostic",
        "confidence": 0.93,
        "reason": "'Abuse' is outdated DSM-IV terminology. DSM-5 uses 'use disorder'.",
        "suggested_rewrite": "substance use disorder / alcohol use disorder"
    },
]


def mock_detect(note_text: str) -> list[dict]:
    flags = []
    seen = set()
    text_lower = note_text.lower()
    for rule in MOCK_PATTERNS:
        for match in re.finditer(rule["pattern"], text_lower):
            span = note_text[match.start():match.end()]
            if span.lower() in seen:
                continue
            seen.add(span.lower())
            flags.append({
                "flagged_span": span,
                "category": rule["category"],
                "confidence": rule["confidence"],
                "reason": rule["reason"],
                "suggested_rewrite": rule["suggested_rewrite"],
            })
    flags.sort(key=lambda f: f["confidence"], reverse=True)
    return flags


# ── Real Claude detection with tool use ───────────────────────────────────────

def claude_detect(note_text: str, patient_id: str = None) -> dict:
    import anthropic
    from prompt import SYSTEM_PROMPT

    fhir_base = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = [{
        "role": "user",
        "content": (
            f"Analyze the following clinical note for stigmatizing language.\n\n"
            f"Patient ID: {patient_id or 'unknown'}\n\n"
            f"Use your tools to retrieve patient context before analyzing the note.\n\n"
            f"---\n\n{note_text}"
        )
    }]

    tool_calls_log = []

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"[agent] Tool call: {block.name}({block.input})")
                    result = _execute_tool(block.name, block.input, fhir_base)
                    summary = _summarize_tool_result(block.name, result)
                    label = _tool_label(block.name)
                    print(f"[agent] Result: {summary}")
                    tool_calls_log.append({"tool": block.name, "label": label, "summary": summary})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        else:
            raw = next((b.text for b in response.content if hasattr(b, "text")), "{}")
            flags = _parse_flags(raw)
            return {"flags": flags, "tool_calls": tool_calls_log}


# ── Public interface ──────────────────────────────────────────────────────────

def detect_stigma(note_text: str, patient_id: str = None) -> dict:
    if USE_MOCK:
        print("[agent] Using mock detection (no ANTHROPIC_API_KEY set)")
        return {"flags": mock_detect(note_text), "tool_calls": []}
    return claude_detect(note_text, patient_id)
