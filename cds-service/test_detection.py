"""
Quick test: fetch Traci Wiegand's alcohol withdrawal note from HAPI and run detection.
Usage: python test_detection.py
"""
import os, json, base64, urllib.request
from agent import detect_stigma

FHIR_BASE = os.environ.get("FHIR_BASE_URL", "http://host.docker.internal:8080/fhir")
DOC_ID    = "4368"   # Traci Wiegand — ED Visit: Alcohol Withdrawal
PATIENT_ID = "4208"

def fetch_note(doc_id: str) -> str:
    url = f"{FHIR_BASE}/DocumentReference/{doc_id}"
    with urllib.request.urlopen(url) as res:
        doc = json.load(res)
    b64 = doc["content"][0]["attachment"]["data"]
    return base64.b64decode(b64).decode("utf-8")

def main():
    print(f"Fetching note {DOC_ID} for patient {PATIENT_ID}...")
    note = fetch_note(DOC_ID)
    print(f"Note length: {len(note)} chars\n")

    print("Running stigma detection...\n")
    flags = detect_stigma(note, patient_id=PATIENT_ID)

    if not flags:
        print("No flags returned.")
        return

    print(f"{len(flags)} flag(s) found:\n")
    for i, f in enumerate(flags, 1):
        conf = f.get("confidence", 0)
        indicator = "CRITICAL" if conf >= 0.85 else "WARNING" if conf >= 0.5 else "INFO"
        print(f"[{i}] [{indicator}] {f.get('flagged_span','?')!r}")
        print(f"     Category   : {f.get('category','?')}")
        print(f"     Confidence : {conf:.2f}")
        print(f"     Reason     : {f.get('reason','?')}")
        print(f"     Rewrite    : {f.get('suggested_rewrite','?')}")
        print()

if __name__ == "__main__":
    main()
