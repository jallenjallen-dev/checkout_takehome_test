"""Streamlit analyst dashboard for chargeback representment workups.

Run: streamlit run app.py

Designed for an analyst working many cases a day: pick a case, see the recommendation and
the requirement-by-requirement evidence assessment at a glance, verify pointers against the
source documents, then edit the rationale / override the action and export.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from chargeback_tool.documents import load_document
from chargeback_tool.engine import analyze_case
from chargeback_tool.models import RepresentmentPack, load_cases

OUTPUT_DIR = Path("outputs")
DOCS_DIR = Path("data/documents")

ACTION_COLORS = {
    "represent": "#1a7f37",          # green
    "request_more_evidence": "#9a6700",  # amber
    "accept_liability": "#cf222e",   # red
}
ACTION_LABEL = {
    "represent": "REPRESENT",
    "request_more_evidence": "REQUEST MORE EVIDENCE",
    "accept_liability": "ACCEPT LIABILITY",
}
STATUS_BADGE = {
    "satisfied": ("✅ satisfied", "#1a7f37"),
    "partial": ("🟡 partial", "#9a6700"),
    "missing": ("❌ missing", "#cf222e"),
}

st.set_page_config(page_title="Chargeback Analyst", layout="wide")


@st.cache_data(show_spinner=False)
def _cases():
    return load_cases()


def _cached_pack_path(case_id: str) -> Path:
    return OUTPUT_DIR / f"{case_id}.json"


def _load_saved_pack(case_id: str) -> RepresentmentPack | None:
    p = _cached_pack_path(case_id)
    if p.exists():
        return RepresentmentPack.model_validate_json(p.read_text())
    return None


def _badge(text: str, color: str) -> str:
    return (
        f"<span style='background:{color};color:white;padding:2px 8px;"
        f"border-radius:6px;font-size:0.85em;font-weight:600'>{text}</span>"
    )


# --------------------------------------------------------------------------- #
# Sidebar: case list
# --------------------------------------------------------------------------- #
cases = _cases()
case_by_id = {c.case_id: c for c in cases}

st.sidebar.title("Chargeback cases")
st.sidebar.caption("AI first-pass workup — analyst reviews & overrides")

labels = []
for c in cases:
    saved = _load_saved_pack(c.case_id)
    badge = ""
    if saved:
        badge = {"represent": "🟢", "request_more_evidence": "🟡", "accept_liability": "🔴"}.get(
            saved.recommended_action, ""
        )
    labels.append(f"{badge} {c.case_id} · {c.transaction.merchant_name}")

idx = st.sidebar.radio(
    "Select a case", range(len(cases)), format_func=lambda i: labels[i], label_visibility="collapsed"
)
case = cases[idx]

# --------------------------------------------------------------------------- #
# Main: header + run control
# --------------------------------------------------------------------------- #
st.title(f"{case.case_id} — {case.transaction.merchant_name}")
st.markdown(
    f"**{case.scheme.upper()} {case.reason_code}** · {case.reason_code_label} · "
    f"**{case.chargeback_amount.value} {case.chargeback_amount.currency}** · "
    f"chargeback raised {case.chargeback_date}"
)

session_key = f"pack::{case.case_id}"
if session_key not in st.session_state:
    st.session_state[session_key] = _load_saved_pack(case.case_id)

col_run, col_status = st.columns([1, 3])
with col_run:
    if st.button("▶ Run analysis", type="primary"):
        with st.spinner("Analysing case and evidence…"):
            try:
                pack = analyze_case(case)
                st.session_state[session_key] = pack
                OUTPUT_DIR.mkdir(exist_ok=True)
                _cached_pack_path(case.case_id).write_text(json.dumps(pack.model_dump(), indent=2))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Analysis failed: {exc}")
with col_status:
    if st.session_state[session_key] is None:
        st.info("No workup yet. Click **Run analysis** (uses your OpenAI key).")

# --------------------------------------------------------------------------- #
# Case context (always visible)
# --------------------------------------------------------------------------- #
with st.expander("Case metadata & issuer narrative", expanded=st.session_state[session_key] is None):
    txn = case.transaction
    c1, c2 = st.columns(2)
    c1.markdown(
        f"**Transaction**\n\n"
        f"- ID: `{txn.transaction_id}`\n"
        f"- Date: {txn.transaction_date}\n"
        f"- Amount: {txn.amount.value} {txn.amount.currency}\n"
        f"- MCC: {txn.merchant_mcc}\n"
        f"- AVS: `{txn.avs_result}` · CVV: `{txn.cvv_result}` · 3DS: `{txn.three_ds_status}`"
    )
    c2.markdown(
        f"**Addresses & device**\n\n"
        f"- Billing postcode: `{txn.billing_address_postcode}`\n"
        f"- Shipping postcode: `{txn.shipping_address_postcode}`\n"
        f"- BIN country: `{txn.card_bin_country}`\n"
        f"- IP: `{txn.ip_address}`\n"
        f"- Device: `{txn.device_fingerprint}`"
    )
    st.markdown(f"**Issuer narrative**\n\n> {case.issuer_narrative}")

pack: RepresentmentPack | None = st.session_state[session_key]

# --------------------------------------------------------------------------- #
# Workup
# --------------------------------------------------------------------------- #
if pack is not None:
    color = ACTION_COLORS[pack.recommended_action]
    st.markdown(
        f"### Recommendation: {_badge(ACTION_LABEL[pack.recommended_action], color)} "
        f"&nbsp; <span style='color:gray'>confidence: {pack.confidence}</span>",
        unsafe_allow_html=True,
    )
    st.caption(pack.justification)
    if not pack.action_agreement:
        st.warning(
            f"Rule-based engine recommends **{ACTION_LABEL[pack.recommended_action]}**, but the "
            f"model independently suggested **{pack.model_suggested_action}**. Worth a closer look."
        )
    if pack.flags:
        st.markdown(" ".join(_badge(f, "#57606a") for f in pack.flags), unsafe_allow_html=True)

    st.markdown(f"**Reason code summary** — {pack.reason_code_summary}")

    st.subheader(
        f"Evidence assessment "
        f"({pack.satisfied_count}/{pack.required_count} satisfied · rule: {pack.requirement_match_rule})"
    )
    for i, a in enumerate(pack.evidence_assessment, start=1):
        label, scolor = STATUS_BADGE.get(a.status, (a.status, "#57606a"))
        st.markdown(
            f"{_badge(label, scolor)} &nbsp; **{i}. {a.requirement}**", unsafe_allow_html=True
        )
        st.markdown(
            f"&nbsp;&nbsp;&nbsp;&nbsp;📎 `{a.evidence_pointer}` — {a.explanation}",
            unsafe_allow_html=True,
        )

    if pack.merchant_followup_requests:
        st.subheader("Merchant follow-up requests")
        for r in pack.merchant_followup_requests:
            st.markdown(f"- {r}")

    if pack.notes:
        with st.expander("Engine notes (document loading)"):
            for n in pack.notes:
                st.markdown(f"- {n}")

    # ----- Analyst override panel -----
    st.subheader("Analyst review & override")
    actions = ["represent", "request_more_evidence", "accept_liability"]
    o1, o2 = st.columns([1, 2])
    override = o1.selectbox(
        "Final action",
        actions,
        index=actions.index(pack.recommended_action),
        format_func=lambda a: ACTION_LABEL[a],
    )
    edited_rationale = o2.text_area(
        "Representment rationale (editable)", value=pack.representment_rationale, height=140
    )
    analyst_notes = st.text_area("Analyst notes (optional)", value="", height=80)

    final = pack.model_dump()
    final.update(
        {
            "analyst_final_action": override,
            "analyst_edited_rationale": edited_rationale,
            "analyst_notes": analyst_notes,
            "analyst_overrode": override != pack.recommended_action,
        }
    )
    st.download_button(
        "⬇ Export final pack (JSON)",
        data=json.dumps(final, indent=2),
        file_name=f"{pack.case_id}_final.json",
        mime="application/json",
    )

# --------------------------------------------------------------------------- #
# Document viewer (verify pointers against source)
# --------------------------------------------------------------------------- #
st.subheader("Source documents")
if not case.merchant_evidence_documents:
    st.caption("No merchant evidence documents submitted for this case.")
for fname in case.merchant_evidence_documents:
    with st.expander(fname):
        doc = load_document(fname)
        if doc.kind == "image":
            st.image(str(DOCS_DIR / fname))
        elif doc.kind == "pdf":
            st.text(doc.text or "(no extractable text)")
        else:
            st.warning(f"Unavailable: {doc.note}")
        path = DOCS_DIR / fname
        if path.exists():
            st.download_button(
                "Download", data=path.read_bytes(), file_name=fname, key=f"dl_{fname}"
            )
