"""CLI for the chargeback representment workup tool.

Examples:
    python cli.py --case CB-2025-0001
    python cli.py --all
    python cli.py --case CB-2025-0004 --quiet   # JSON only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from chargeback_tool.engine import analyze_case
from chargeback_tool.models import RepresentmentPack, load_case, load_cases

OUTPUT_DIR = Path("outputs")

_ACTION_LABEL = {
    "represent": "REPRESENT",
    "accept_liability": "ACCEPT LIABILITY",
    "request_more_evidence": "REQUEST MORE EVIDENCE",
}
_STATUS_MARK = {"satisfied": "[+]", "partial": "[~]", "missing": "[-]"}


def _print_pack(pack: RepresentmentPack) -> None:
    print("=" * 78)
    print(f"{pack.case_id}  |  {pack.merchant_name}  |  {pack.scheme} {pack.reason_code} "
          f"({pack.reason_code_label})")
    print(f"Amount: {pack.chargeback_amount.value} {pack.chargeback_amount.currency}")
    print("=" * 78)
    print(f"\nRECOMMENDED ACTION: {_ACTION_LABEL[pack.recommended_action]}  "
          f"(confidence: {pack.confidence})")
    print(f"  -> {pack.justification}")
    if not pack.action_agreement:
        print(f"  ! model suggested '{pack.model_suggested_action}' "
              f"(rule-based engine overrode to '{pack.recommended_action}')")
    if pack.flags:
        print(f"  flags: {', '.join(pack.flags)}")

    print(f"\nREASON CODE SUMMARY\n  {pack.reason_code_summary}")

    print(f"\nEVIDENCE ASSESSMENT  (rule: {pack.requirement_match_rule}, "
          f"{pack.satisfied_count}/{pack.required_count} satisfied needed)")
    for i, a in enumerate(pack.evidence_assessment, start=1):
        print(f"  {_STATUS_MARK.get(a.status, '[?]')} {i}. {a.status.upper()} "
              f"-- {a.requirement}")
        print(f"        pointer: {a.evidence_pointer}")
        print(f"        {a.explanation}")

    print(f"\nREPRESENTMENT RATIONALE\n  {pack.representment_rationale}")

    if pack.merchant_followup_requests:
        print("\nMERCHANT FOLLOW-UP REQUESTS")
        for r in pack.merchant_followup_requests:
            print(f"  - {r}")

    if pack.notes:
        print("\nNOTES")
        for n in pack.notes:
            print(f"  - {n}")
    print()


def _save_pack(pack: RepresentmentPack) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"{pack.case_id}.json"
    out.write_text(json.dumps(pack.model_dump(), indent=2))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Chargeback representment workup tool")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--case", help="Case id, e.g. CB-2025-0001")
    g.add_argument("--all", action="store_true", help="Process every case in cases.json")
    parser.add_argument("--data", default="data/cases.json", help="Path to cases.json")
    parser.add_argument("--model", default=None, help="Override OPENAI_MODEL")
    parser.add_argument("--quiet", action="store_true", help="Print JSON only (no summary)")
    parser.add_argument("--no-save", action="store_true", help="Do not write to outputs/")
    args = parser.parse_args()

    cases = [load_case(args.case, args.data)] if args.case else load_cases(args.data)

    for case in cases:
        try:
            pack = analyze_case(case, model=args.model)
        except Exception as exc:  # noqa: BLE001 - take-home: report and continue
            print(f"ERROR analysing {case.case_id}: {exc}", file=sys.stderr)
            continue

        if args.quiet:
            print(json.dumps(pack.model_dump(), indent=2))
        else:
            _print_pack(pack)

        if not args.no_save:
            path = _save_pack(pack)
            if not args.quiet:
                print(f"saved -> {path}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
