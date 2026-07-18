# StigmaGuard — Real-Time Clinical Documentation Review

StigmaGuard is a FHIR-native clinical documentation review service that evaluates clinical notes before signing, explains potentially stigmatizing language, and suggests patient-centered alternatives while keeping the clinician in control.

Built at the Anthropic / Abridge / Lightspeed Healthcare Hackathon, July 2026.

> **Status:** This repository contains a hackathon prototype demonstrating a standards-based approach to real-time clinical documentation review. The focus is on workflow integration, explainable AI, and FHIR/CDS Hooks interoperability.

---

# The Problem

Language in the medical record influences future clinical decision making as well as future patient engagement with the system.

Terms such as *"addict," "drug-seeking," "non-compliant,"* and *"dirty urine"* have been shown to contribute to clinician bias and can persist throughout a patient's longitudinal record.

Research has documented this problem since at least 2018 (Goddu et al.), and multiple studies have suggested real-time documentation review as a future direction.

More recently, Zhou et al. (UC Irvine, arXiv 2606.00019) demonstrated that stigmatizing language is often introduced during clinician editing of ambient AI drafts rather than by the ambient AI system itself, making note signing a particularly valuable intervention point.

---

# What Was Built

- **FHIR-backed EMR simulation** using HAPI FHIR with patient charts and documentation
- **CDS Hooks note-sign service** integrated into the documentation workflow
- **Context-aware documentation review** using Claude Haiku with tool use
- **Tiered intervention interface** with confidence-based findings, explanations, suggested rewrites, note highlighting, and clinician accept/reject controls

Unlike keyword matching, recommendations are generated **after retrieving structured patient context** including demographics, active conditions, social history, and prior documentation.

---

# Prior Work

The documentation review agent was informed by ongoing research that is not part of the hackathon submission, including:

- Clinician-developed stigma taxonomy and adjudication rubric
- Synthetic benchmark for stigmatizing language detection (in preparation)
- Evaluation of locally deployed LLMs for privacy-preserving stigma detection (https://www.medrxiv.org/content/10.64898/2026.05.29.26354402v1)
- Synthetic benchmarking methodology for context-aware clinical language evaluation

---

# Workflow

```
Clinician edits note
          │
          ▼
      Sign Note
          │
          ▼
CDS Hooks (note-sign)
          │
          ▼
Retrieve Patient Context
(FHIR Resources)
          │
          ▼
Documentation Review
          │
          ▼
Accept / Reject Suggestions
          │
          ▼
Finalize Note
```

The clinician always retains final authority over documentation.

---

# Architecture

```
Browser (emr.html)
        │
        ├─────────────── HAPI FHIR (8080)
        │                    │
        │                    ├── Patient
        │                    ├── Conditions
        │                    ├── Social History
        │                    └── Prior Notes
        │
        ▼
CDS Service (Flask)
        │
        ▼
Claude Haiku Agent
        │
        ├── get_patient_info()
        ├── get_patient_conditions()
        ├── get_social_history()
        └── get_prior_notes()
```

The review engine retrieves structured patient context before evaluating documentation.

Clinical context—including housing instability, bereavement, employment status, active diagnoses, and prior documentation patterns—is incorporated into the review process so recommendations are generated with greater contextual awareness than simple keyword matching.

---

# Quickstart

## Prerequisites

- Docker Desktop
- Python 3.11+
- Anthropic API Key (optional)

---

## 1. Start HAPI FHIR

```bash
docker compose up -d
```

FHIR server:

```
http://localhost:8080/fhir
```

---

## 2. Start the CDS Service

```bash
cd cds-service

cp ../.env.example .env

pip install -r requirements.txt

python app.py
```

Runs on:

```
http://localhost:8004
```

If no Anthropic API key is configured, the application automatically falls back to a lightweight regex-based mock detector for demonstration purposes.

---

## 3. Launch the EMR

```bash
cd frontend

python3 -m http.server 3000
```

Navigate to:

```
http://localhost:3000/emr.html
```

The frontend must be served over HTTP (not `file://`) due to browser CORS restrictions.

---

# Documentation Review

The review engine uses a clinician-developed twelve-category taxonomy.

| Category | Example | Preferred |
|------------|-----------------|-----------------------------|
| Identity Labels | addict | person with opioid use disorder |
| Behavioral Framing | non-compliant | describe barriers or symptoms |
| Distrust Language | claims | neutral clinical reporting |
| Moral Judgment | dirty urine | positive / negative toxicology |
| Clinical Terminology | substance abuse | substance use disorder |
| Person-First Language | the alcoholic | patient with alcohol use disorder |

Each finding includes:

- Highlighted text span
- Classification category
- Confidence score
- Clinical rationale
- Suggested rewrite

Confidence scores drive UI severity:

- **Critical** ≥ 0.85
- **Warning** ≥ 0.50
- **Informational** < 0.50

---

# Why CDS Hooks?

CDS Hooks is the HL7 standard for embedding decision support into EHR workflows.

Although the official hook catalog includes ordering, scheduling, prescribing, and encounter workflows, it does not currently define a note-sign event.

This prototype demonstrates how a standards-compliant custom `note-sign` hook can be implemented using the CDS Hooks extension mechanism.

The same workflow currently used for clinical documentation improvement (CDI) can also support documentation quality, patient-centered language, and clinician education without disrupting existing workflows.

---

# Future Directions

This prototype demonstrates a general documentation review framework rather than a single detector.

The same architecture could support additional review modules including:

- Diagnostic ambiguity
- Health literacy
- Documentation completeness
- Billing and CDI support
- Clinical guideline adherence
- Safety language review

---

# References

- Goddu AP, et al. *Do Words Matter? Stigmatizing Language and the Transmission of Bias in the Medical Record.* J Gen Intern Med. 2018.
- Sethi et al. npj Health Syst. 2026;3:15.
doi:10.1038/s44401-026-00069-0
- Zhou et al. *Ambient AI Documentation and Stigmatizing Language.* arXiv:2606.00019.
- HL7 CDS Hooks Specification
- DSM-5 Terminology Guidance (American Psychiatric Association)