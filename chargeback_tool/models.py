"""Pydantic schemas: input cases, the LLM's structured analysis, and the final pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Input case schema (mirrors cases.json)
# --------------------------------------------------------------------------- #


class Money(BaseModel):
    value: float
    currency: str


class Transaction(BaseModel):
    transaction_id: str
    merchant_name: str
    merchant_mcc: str
    transaction_date: str
    amount: Money
    card_bin_country: Optional[str] = None
    avs_result: Optional[str] = None
    cvv_result: Optional[str] = None
    three_ds_status: Optional[str] = None
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None
    billing_address_postcode: Optional[str] = None
    shipping_address_postcode: Optional[str] = None


class Case(BaseModel):
    case_id: str
    scheme: str
    reason_code: str
    reason_code_label: str
    chargeback_date: str
    chargeback_amount: Money
    transaction: Transaction
    issuer_narrative: str
    merchant_evidence_documents: list[str] = Field(default_factory=list)


def load_cases(path: str | Path = "data/cases.json") -> list[Case]:
    raw = json.loads(Path(path).read_text())
    return [Case.model_validate(c) for c in raw]


def load_case(case_id: str, path: str | Path = "data/cases.json") -> Case:
    for case in load_cases(path):
        if case.case_id == case_id:
            return case
    raise KeyError(f"Case {case_id!r} not found in {path}")


# --------------------------------------------------------------------------- #
# LLM structured output (what the model fills in)
# --------------------------------------------------------------------------- #

Status = Literal["satisfied", "partial", "missing"]
Action = Literal["represent", "accept_liability", "request_more_evidence"]
Confidence = Literal["high", "medium", "low"]


class EvidenceAssessment(BaseModel):
    requirement: str = Field(description="The compelling-evidence requirement being assessed.")
    status: Status
    evidence_pointer: str = Field(
        description="Where the evidence appears: filename and page/locator, e.g. "
        "'CB-2025-0007_consolidated_manifest.pdf p.4'. Use 'none' if not found."
    )
    explanation: str = Field(
        description="One or two sentences: what was found (or not) and why it does or "
        "does not satisfy the requirement."
    )


class LLMAnalysis(BaseModel):
    """The model's judgement. Python computes the final recommended_action from this."""

    reason_code_summary: str = Field(
        description="Plain-English restatement of what the issuer alleges and what "
        "compelling evidence the scheme requires to defend it."
    )
    evidence_assessment: list[EvidenceAssessment]
    representment_rationale: str = Field(
        description="3-5 sentences, ready for the analyst to edit and file."
    )
    suggested_action: Action = Field(
        description="The model's own view of the action, before Python applies rule logic."
    )
    justification: str = Field(description="One line justifying the action.")
    merchant_followup_requests: list[str] = Field(
        description="Specific items to request from the merchant. Empty unless evidence "
        "is fixably incomplete."
    )
    confidence: Confidence
    flags: list[str] = Field(
        description="Short quick-glance warnings, e.g. 'address_mismatch', "
        "'image_only_evidence', 'evidence_buried_in_document', 'non_representable_code'."
    )


# --------------------------------------------------------------------------- #
# Final analyst-ready pack
# --------------------------------------------------------------------------- #


class RepresentmentPack(BaseModel):
    case_id: str
    scheme: str
    reason_code: str
    reason_code_label: str
    chargeback_amount: Money
    merchant_name: str

    reason_code_summary: str
    requirement_match_rule: str  # ALL | ANY_TWO | ANY_ONE
    required_count: int
    satisfied_count: int

    evidence_assessment: list[EvidenceAssessment]
    representment_rationale: str

    recommended_action: Action  # computed in Python from the rule + statuses
    model_suggested_action: Action  # the LLM's own view, for transparency
    action_agreement: bool  # whether the two agree
    justification: str
    merchant_followup_requests: list[str]

    confidence: Confidence
    flags: list[str]
    documents: list[str]
    notes: list[str] = Field(default_factory=list)  # engine-level notes (e.g. missing files)
