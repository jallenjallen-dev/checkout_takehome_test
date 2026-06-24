"""Structured compelling-evidence requirements per reason code.

Encoded from the simplified take-home rules ("Reason Codes.pdf"). These are NOT a
substitute for real Visa VCR / Mastercard Chargeback Guide rules.

Each rule carries:
  - match_rule: how many requirements must be satisfied for a defensible representment
      ALL      -> every requirement
      ANY_TWO  -> at least two
      ANY_ONE  -> at least one
  - representable: False for codes that generally cannot be won (recommend accept_liability)
  - requirements: the individual compelling-evidence items the merchant must show
"""

from __future__ import annotations

from dataclasses import dataclass, field

ALL = "ALL"
ANY_TWO = "ANY_TWO"
ANY_ONE = "ANY_ONE"


@dataclass(frozen=True)
class ReasonCode:
    code: str
    scheme: str  # "visa" | "mastercard"
    label: str
    issuer_claim: str
    match_rule: str
    requirements: list[str]
    representable: bool = True
    note: str = ""

    def required_count(self) -> int:
        """How many requirements must be satisfied to clear the bar."""
        if self.match_rule == ALL:
            return len(self.requirements)
        if self.match_rule == ANY_TWO:
            return 2
        if self.match_rule == ANY_ONE:
            return 1
        raise ValueError(f"Unknown match_rule {self.match_rule!r}")


REASON_CODES: dict[str, ReasonCode] = {
    "10.4": ReasonCode(
        code="10.4",
        scheme="visa",
        label="Other Fraud - Card Absent Environment",
        issuer_claim="Cardholder denies authorising a card-not-present transaction.",
        match_rule=ANY_TWO,
        requirements=[
            "Evidence the cardholder used the same card and same shipping address in two "
            "prior undisputed transactions with this merchant, completed more than 120 days "
            "but less than 365 days before the disputed transaction",
            "Evidence the cardholder is in possession of and using the merchandise "
            "(e.g. signed-in account activity post-delivery, social media post tagging the merchant)",
            "For digital goods: device fingerprint, IP address, geolocation, and customer "
            "account login matching prior undisputed transactions",
            "Proof of delivery to the cardholder's verified billing address (not just shipping "
            "address) with signature confirmation",
        ],
    ),
    "10.5": ReasonCode(
        code="10.5",
        scheme="visa",
        label="Visa Fraud Monitoring Program",
        issuer_claim="Transaction flagged under Visa's fraud monitoring program.",
        match_rule=ALL,
        requirements=[
            "Proof the transaction was miscoded by the issuer (the only path to represent)",
        ],
        representable=False,
        note="Generally cannot be represented. Recommend accept_liability unless the "
        "merchant can prove the transaction was miscoded by the issuer.",
    ),
    "12.5": ReasonCode(
        code="12.5",
        scheme="visa",
        label="Incorrect Amount",
        issuer_claim="The amount charged does not match the amount the cardholder authorised.",
        match_rule=ALL,
        requirements=[
            "The signed receipt, terms of service, or order confirmation showing the amount "
            "the cardholder agreed to",
            "Documentation showing the amount charged matches that agreed amount",
            "If a tip, gratuity, or adjustment was added, evidence the cardholder authorised it",
        ],
    ),
    "12.6.1": ReasonCode(
        code="12.6.1",
        scheme="visa",
        label="Duplicate Processing",
        issuer_claim="The same transaction was processed more than once.",
        match_rule=ALL,
        requirements=[
            "Evidence the two transactions are for two separate purchases "
            "(e.g. different order IDs, different items, different services rendered)",
            "Documentation of each purchase event (separate invoices, separate delivery "
            "confirmations, separate service dates)",
            "Transaction timestamps and authorisation codes for each charge",
        ],
    ),
    "13.1": ReasonCode(
        code="13.1",
        scheme="visa",
        label="Merchandise / Services Not Received",
        issuer_claim="Cardholder paid but never received the goods or services.",
        match_rule=ALL,
        requirements=[
            "Proof the goods were delivered OR the service was rendered: for merchandise, "
            "tracking number, carrier name, and confirmation of delivery to the cardholder's "
            "address; for services, evidence the service was rendered on or before the "
            "expected date (booking confirmation, attendance log, access logs)",
            "Date of delivery / service rendered is on or before the chargeback date",
            "The delivery address materially matches the address provided by the cardholder "
            "at purchase",
        ],
    ),
    "13.2": ReasonCode(
        code="13.2",
        scheme="visa",
        label="Cancelled Recurring Transaction",
        issuer_claim="Cardholder cancelled a recurring subscription but was still charged.",
        match_rule=ALL,
        requirements=[
            "Terms of service disclosing the recurring billing arrangement and the "
            "cancellation method",
            "Evidence the cardholder was notified of the upcoming charge (typically 7+ days "
            "in advance) for transactions over a defined threshold",
            "No record of the cardholder having submitted a cancellation request prior to "
            "the billing date",
            "Evidence of the cardholder's original opt-in to the recurring arrangement",
        ],
    ),
    "13.3": ReasonCode(
        code="13.3",
        scheme="visa",
        label="Not as Described or Defective Merchandise",
        issuer_claim="Cardholder received the goods but they are materially not as described "
        "or defective.",
        match_rule=ALL,
        requirements=[
            "The merchant's published description of the item the cardholder purchased",
            "Evidence the item delivered matches that description "
            "(photos, specs, serial number match)",
            "Evidence the merchant offered a return/refund route and the cardholder did not "
            "use it, OR evidence the cardholder used and retained the merchandise after "
            "raising the complaint",
        ],
    ),
    "13.6": ReasonCode(
        code="13.6",
        scheme="visa",
        label="Credit Not Processed",
        issuer_claim="The merchant agreed to a refund but never processed it.",
        match_rule=ANY_ONE,
        requirements=[
            "Evidence that a refund was processed (refund transaction ID, date, amount)",
            "Evidence that no refund was ever agreed (merchant's refund policy and absence "
            "of any refund commitment in cardholder communications)",
        ],
    ),
    "13.7": ReasonCode(
        code="13.7",
        scheme="visa",
        label="Cancelled Merchandise / Services",
        issuer_claim="Cardholder cancelled the purchase per the merchant's policy but was charged.",
        match_rule=ALL,
        requirements=[
            "The merchant's cancellation policy as displayed at point of sale",
            "Evidence the cardholder agreed to that policy "
            "(e.g. checkbox click record, signed terms)",
            "Evidence the cardholder either did not cancel within the policy window, or "
            "cancelled outside the refundable period",
        ],
    ),
    "4837": ReasonCode(
        code="4837",
        scheme="mastercard",
        label="No Cardholder Authorisation",
        issuer_claim="Cardholder denies authorising the transaction "
        "(card-not-present fraud equivalent).",
        match_rule=ANY_TWO,
        requirements=[
            "AVS match (full address) AND CVV match on the disputed transaction",
            "3D Secure authentication completed successfully "
            "(Mastercard SecureCode / Identity Check)",
            "Two prior undisputed transactions from the same cardholder with this merchant "
            "in the past 12 months, with matching billing details",
            "Proof of delivery to the cardholder's billing address with signature",
        ],
    ),
    "4853": ReasonCode(
        code="4853",
        scheme="mastercard",
        label="Cardholder Dispute (Goods / Services Not Provided)",
        issuer_claim="Goods or services were not provided as agreed.",
        match_rule=ALL,
        requirements=[
            "Proof of delivery or service provision (tracking, confirmation, access log)",
            "Evidence the goods or services materially match what was advertised",
            "Either: no contact from the cardholder attempting to resolve the issue before "
            "the chargeback, OR documentation showing the merchant attempted resolution and "
            "the cardholder refused",
        ],
    ),
    "4855": ReasonCode(
        code="4855",
        scheme="mastercard",
        label="Goods / Services Not Provided",
        issuer_claim="Paid for goods or services that were never delivered or rendered.",
        match_rule=ALL,
        requirements=[
            "Proof of delivery (tracking + carrier confirmation) or proof of service "
            "rendered (access logs, attendance, completed booking)",
            "Date of delivery / service is before the chargeback date",
            "Delivery address matches the cardholder's records",
        ],
    ),
    "4859": ReasonCode(
        code="4859",
        scheme="mastercard",
        label="No-Show / Addendum",
        issuer_claim="Cardholder disputes a no-show fee, late cancellation fee, or addendum "
        "charge (common in hospitality, car rental, travel).",
        match_rule=ALL,
        requirements=[
            "Evidence of the cardholder's original reservation or booking",
            "The merchant's no-show / cancellation policy as disclosed at booking",
            "Evidence the cardholder either failed to show or cancelled outside the policy window",
            "Evidence the fee charged matches the policy disclosed",
        ],
    ),
    "4863": ReasonCode(
        code="4863",
        scheme="mastercard",
        label="Cardholder Does Not Recognise - Potential Fraud",
        issuer_claim="Cardholder does not recognise the transaction (may be a confusing "
        "descriptor rather than actual fraud).",
        match_rule=ANY_ONE,
        requirements=[
            "Evidence the merchant's billing descriptor matches the merchant name the "
            "cardholder would recognise",
            "AVS + CVV match on the disputed transaction",
            "Prior undisputed transactions from the same cardholder with this merchant",
            "Cardholder's IP / device / account login matching prior undisputed sessions",
        ],
    ),
    "4870": ReasonCode(
        code="4870",
        scheme="mastercard",
        label="Chip Liability Shift",
        issuer_claim="Counterfeit card used at a non-chip-enabled terminal (card-present only).",
        match_rule=ALL,
        requirements=[
            "Card-present chip/terminal evidence (not applicable to a CNP acquiring exercise)",
        ],
        representable=False,
        note="Card-present reason code. For a CNP-focused exercise expect accept_liability - "
        "flag the merchant for terminal upgrade and move on.",
    ),
}


def get_reason_code(code: str) -> ReasonCode | None:
    return REASON_CODES.get(code)
