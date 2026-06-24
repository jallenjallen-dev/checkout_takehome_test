"""Core flow: analyze_case(case) -> RepresentmentPack.

The LLM judges each compelling-evidence requirement (satisfied/partial/missing) with a
citation. Python then applies the reason code's match rule (ALL / ANY_TWO / ANY_ONE) to
compute the final recommended_action, so the verdict is consistent and auditable rather
than left to the model's tone.
"""

from __future__ import annotations

import json

from . import llm
from .documents import LoadedDocument, load_documents
from .models import (
    Action,
    Case,
    EvidenceAssessment,
    LLMAnalysis,
    Money,
    RepresentmentPack,
)
from .reason_codes import ReasonCode, get_reason_code

SYSTEM_PROMPT = """\
You are a chargeback representment analyst's assistant for a payment acquirer. You produce \
a first-pass workup that a human analyst will review, edit, and file. Be precise and \
sceptical.

Rules:
- Assess the merchant's evidence ONLY against the specific compelling-evidence \
requirements you are given. Return exactly one assessment per requirement, in the same \
order, copying the requirement text.
- Status: "satisfied" only if the evidence clearly and specifically meets the requirement; \
"partial" if related evidence exists but is incomplete, ambiguous, or mismatched; \
"missing" if nothing addresses it.
- Do NOT be swayed by confident tone, neat tables, internal scores, or a merchant's \
"we are confident this is legitimate" conclusion. Confident-sounding evidence that does \
not map to a requirement is still "missing".
- Always cite where evidence appears using the document filename and page tag shown in \
the evidence, e.g. "CB-2025-0007_consolidated_manifest.pdf p.4". Use "none" if not found.
- Cross-check names, addresses, dates and amounts against the transaction metadata. A \
delivery to a different address than the cardholder's does NOT satisfy a delivery-address \
requirement (flag "address_mismatch"). Delivery/service dates must be on or before the \
chargeback date.
- Set flags for quick analyst triage, e.g. "address_mismatch", "image_only_evidence", \
"evidence_buried_in_document", "date_after_chargeback", "non_representable_code", \
"confident_but_irrelevant_evidence".
- representment_rationale: 3-5 sentences the analyst can edit and file.
- merchant_followup_requests: only fill when specific, obtainable evidence would close a \
gap; otherwise leave empty.
"""


def _format_requirements(rc: ReasonCode) -> str:
    rule_text = {
        "ALL": "ALL of these requirements must be satisfied.",
        "ANY_TWO": "ANY TWO of these requirements must be satisfied.",
        "ANY_ONE": "ANY ONE of these requirements must be satisfied.",
    }[rc.match_rule]
    lines = [f"{i}. {req}" for i, req in enumerate(rc.requirements, start=1)]
    note = f"\nScheme note: {rc.note}" if rc.note else ""
    return f"Match rule: {rule_text}\n" + "\n".join(lines) + note


def _evidence_parts(docs: list[LoadedDocument]) -> list[dict]:
    """Build OpenAI content parts (text + images) from loaded documents."""
    parts: list[dict] = []
    for d in docs:
        if d.kind == "pdf":
            header = f"\n===== DOCUMENT: {d.filename} (PDF text) ====="
            if d.note:
                header += f"\n(note: {d.note})"
            parts.append({"type": "text", "text": f"{header}\n{d.text}"})
        elif d.kind == "image":
            parts.append(
                {"type": "text", "text": f"\n===== DOCUMENT: {d.filename} (image below) ====="}
            )
            parts.append({"type": "image_url", "image_url": {"url": d.image_data_url}})
        else:  # missing / unreadable
            parts.append(
                {"type": "text", "text": f"\n===== DOCUMENT: {d.filename} - UNAVAILABLE ({d.note}) ====="}
            )
    if not docs:
        parts.append({"type": "text", "text": "\n(No merchant evidence documents were submitted.)"})
    return parts


def _case_summary_text(case: Case, rc: ReasonCode) -> str:
    txn = case.transaction
    return (
        f"CHARGEBACK CASE\n"
        f"case_id: {case.case_id}\n"
        f"scheme: {case.scheme}\n"
        f"reason_code: {case.reason_code} - {case.reason_code_label}\n"
        f"issuer_claim (scheme): {rc.issuer_claim}\n"
        f"chargeback_date: {case.chargeback_date}\n"
        f"chargeback_amount: {case.chargeback_amount.value} {case.chargeback_amount.currency}\n\n"
        f"TRANSACTION\n"
        f"merchant: {txn.merchant_name} (MCC {txn.merchant_mcc})\n"
        f"transaction_id: {txn.transaction_id}\n"
        f"transaction_date: {txn.transaction_date}\n"
        f"amount: {txn.amount.value} {txn.amount.currency}\n"
        f"avs_result: {txn.avs_result}  cvv_result: {txn.cvv_result}  "
        f"three_ds_status: {txn.three_ds_status}\n"
        f"card_bin_country: {txn.card_bin_country}\n"
        f"billing_postcode: {txn.billing_address_postcode}  "
        f"shipping_postcode: {txn.shipping_address_postcode}\n"
        f"ip_address: {txn.ip_address}  device_fingerprint: {txn.device_fingerprint}\n\n"
        f"ISSUER NARRATIVE\n{case.issuer_narrative}\n\n"
        f"COMPELLING-EVIDENCE REQUIREMENTS FOR {case.reason_code}\n{_format_requirements(rc)}\n"
    )


def _decide_action(rc: ReasonCode, assessments: list[EvidenceAssessment]) -> tuple[Action, int]:
    """Apply the reason code's match rule. Returns (action, satisfied_count)."""
    satisfied = sum(1 for a in assessments if a.status == "satisfied")
    partial = sum(1 for a in assessments if a.status == "partial")
    required = rc.required_count()

    if not rc.representable:
        # Only winnable in the documented exception (e.g. proven issuer miscoding).
        if satisfied >= required and required > 0:
            return "represent", satisfied
        return "accept_liability", satisfied

    if satisfied >= required:
        return "represent", satisfied
    if satisfied + partial >= 1:
        # Some evidence present but short of the bar -> worth chasing the gap.
        return "request_more_evidence", satisfied
    return "accept_liability", satisfied


def analyze_case(case: Case, model: str | None = None) -> RepresentmentPack:
    rc = get_reason_code(case.reason_code)
    if rc is None:
        raise ValueError(f"Unknown reason code {case.reason_code!r} for case {case.case_id}")

    docs = load_documents(case.merchant_evidence_documents)
    notes = [f"{d.filename}: {d.note}" for d in docs if d.note]

    user_content = [{"type": "text", "text": _case_summary_text(case, rc)}]
    user_content += _evidence_parts(docs)

    analysis: LLMAnalysis = llm.analyse(SYSTEM_PROMPT, user_content, model=model)

    recommended_action, satisfied_count = _decide_action(rc, analysis.evidence_assessment)

    flags = list(analysis.flags)
    if not rc.representable and "non_representable_code" not in flags:
        flags.append("non_representable_code")

    return RepresentmentPack(
        case_id=case.case_id,
        scheme=case.scheme,
        reason_code=case.reason_code,
        reason_code_label=case.reason_code_label,
        chargeback_amount=case.chargeback_amount,
        merchant_name=case.transaction.merchant_name,
        reason_code_summary=analysis.reason_code_summary,
        requirement_match_rule=rc.match_rule,
        required_count=rc.required_count(),
        satisfied_count=satisfied_count,
        evidence_assessment=analysis.evidence_assessment,
        representment_rationale=analysis.representment_rationale,
        recommended_action=recommended_action,
        model_suggested_action=analysis.suggested_action,
        action_agreement=(recommended_action == analysis.suggested_action),
        justification=analysis.justification,
        merchant_followup_requests=analysis.merchant_followup_requests,
        confidence=analysis.confidence,
        flags=flags,
        documents=case.merchant_evidence_documents,
        notes=notes,
    )
