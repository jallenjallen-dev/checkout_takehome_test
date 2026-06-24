# AI-Assisted Chargeback Analyst Tool

Takes a chargeback case (metadata, issuer narrative, reason code, 0–4 merchant evidence
files) and produces an **analyst-ready representment workup**:

> *Here is what the issuer claims, here is what evidence the scheme requires, here is what
> evidence we have and where it appears, and here is whether we should fight or accept
> liability.*

The AI does the first-pass workup — requirement-by-requirement — so an analyst working
~80 cases/day can review and override fast, not research from scratch.

---

## Run it in under 10 minutes

```bash
# 1. Install (Python 3.10+)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Add your OpenAI key
cp .env.example .env
#   then edit .env and set OPENAI_API_KEY=sk-...

# 3. Smoke test (no API call)
python -c "import json; print(len(json.load(open('data/cases.json'))), 'cases loaded')"
# -> 10 cases loaded

# 4. Run one case (calls OpenAI)
python cli.py --case CB-2025-0001

# 5. Run all 10 and save JSON packs to outputs/
python cli.py --all

# 6. Analyst UI
streamlit run app.py
```

`.env` needs `OPENAI_API_KEY`. `OPENAI_MODEL` defaults to `gpt-4o` (any vision-capable
chat model with structured-output support works).

---

## What it produces

For each case, a structured `RepresentmentPack` (see `chargeback_tool/models.py`):

- **`reason_code_summary`** — plain-English restatement of the issuer's claim and what the
  scheme requires.
- **`evidence_assessment[]`** — one entry per compelling-evidence requirement:
  `status` (satisfied / partial / missing), an **`evidence_pointer`** (`filename p.N`),
  and an explanation.
- **`representment_rationale`** — 3–5 sentences, ready for the analyst to edit and file.
- **`recommended_action`** — `represent` / `accept_liability` / `request_more_evidence`
  with a one-line `justification`.
- **`merchant_followup_requests[]`** — populated when more evidence would close a gap.
- **`flags[]`, `confidence`, `notes[]`** — quick-glance triage signals.

---

## How it works

```
case + reason-code requirements + merchant evidence
        │
        ▼
  LLM (structured output)  ── judges each requirement: satisfied/partial/missing + citation
        │
        ▼
  Python rule engine       ── applies the code's match rule -> final recommended_action
        │
        ▼
  RepresentmentPack (JSON) ── CLI prints it / Streamlit displays it
```

Key modules (`chargeback_tool/`):

| file | role |
|------|------|
| `reason_codes.py` | The 15 reason codes as **structured rules** — requirements + match logic (`ALL` / `ANY_TWO` / `ANY_ONE`) + a `representable` flag. |
| `documents.py` | Loads evidence: per-page text from PDFs (for citations), base64 images for PNGs. |
| `models.py` | Pydantic schemas for the input case, the LLM output, and the final pack. |
| `llm.py` | OpenAI structured-output call (`beta.chat.completions.parse`). |
| `engine.py` | `analyze_case()` — builds the prompt, calls the LLM, computes the recommendation. |

### Why the recommendation is computed in Python, not by the LLM
The model judges each requirement independently (with a citation), but the **final
verdict is decided by the rule engine** (`engine._decide_action`) by counting satisfied
requirements against the code's match rule. This keeps the recommendation consistent and
auditable, and stops confident-sounding evidence from talking the model into a "represent".
The model's own suggestion is also kept (`model_suggested_action`); when the two disagree
the output flags it (`action_agreement: false`) so the analyst takes a closer look.

### Document handling tradeoff
The provided PDFs are text-based, so we extract their text directly with `pypdf` and tag
each page (`[filename p.N]`). That is cheap, fast, and gives **precise page-level
citations** — which matters for the case where the real evidence is buried in a multi-page
manifest. The PNGs (a tracking screenshot, a delivery photo) are genuine images, so they
are sent to the **vision model** in the same call. We deliberately did *not* render every
PDF page to an image (uniform vision): it costs far more tokens and produces weaker
citations for no benefit on this dataset. If a PDF turned out to be a scan with no
extractable text, `documents.py` flags it (`no extractable text…`) so the gap is visible
rather than silent.

---

## The analyst UI (`streamlit run app.py`)

- **Left:** case list with a colour dot for the saved recommendation.
- **Main:** recommendation badge + confidence, reason-code summary, and the
  **evidence-assessment list** (status chip · requirement · 📎 pointer · explanation) as
  the centrepiece.
- **Override:** the analyst can change the final action, edit the rationale inline, add
  notes, and **export the final pack as JSON**.
- **Source documents:** each evidence file is viewable inline (image render / extracted
  PDF text) so a pointer can be verified in one click.

Results are cached to `outputs/<case_id>.json` so reopening a case doesn't re-spend tokens.

---

## Notes & scope

- Reason-code rules are the **simplified take-home set** only — not real Visa VCR /
  Mastercard Chargeback Guide rules.
- No production error handling, auth, or deployment (per the brief). Errors per case are
  reported and the run continues.
- All provided data is synthetic.
