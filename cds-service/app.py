import os, json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from agent import detect_stigma
from tiering import flags_to_cards

load_dotenv()

app = Flask(__name__)

@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/cds-services", methods=["GET", "OPTIONS"])
def discovery():
    return jsonify({
        "services": [{
            "hook": "note-sign",
            "id": "note-stigma-detection",
            "title": "Stigma Language Detector",
            "description": "Reviews clinical notes at sign-time for stigmatizing language related to substance use disorder, with patient-centered rewrite suggestions.",
            "prefetch": {}
        }]
    })

@app.route("/cds-services/note-sign", methods=["POST", "OPTIONS"])
def note_sign():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    body = request.get_json(force=True)
    context = body.get("context", {})
    note_text = context.get("noteText", "")
    patient_id = context.get("patientId", "")

    if not note_text.strip():
        return jsonify({"cards": []})

    flags = detect_stigma(note_text, patient_id=patient_id)
    cards = flags_to_cards(flags)
    return jsonify({"cards": cards})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"CDS service running on http://localhost:{port}")
    print(f"Detection mode: {'MOCK (no API key)' if not os.environ.get('ANTHROPIC_API_KEY') else 'Claude API'}")
    app.run(host="0.0.0.0", port=port, debug=True)
