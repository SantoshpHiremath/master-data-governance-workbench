"""
business_rules.py
------------------
Documented master-data business rules, expressed as small, independently
testable, named functions rather than inline validation scattered across
the codebase. This documents data standards, business rules, and process
workflows for master data objects: each rule below IS the documentation, in a form a
governance meeting could review line by line, not a separate Word
document that drifts out of sync with the code.

Each rule returns a RuleViolation (or None if the record passes), so a
caller can collect ALL violations for a record rather than stopping at
the first one — a real governance reviewer wants the full list of
problems on a record, not one at a time.
"""

from dataclasses import dataclass
import re

from .records import CustomerRecord, VendorRecord, MaterialRecord

VALID_ISO_COUNTRY_CODES = {
    "DE", "FR", "IT", "ES", "NL", "BE", "AT", "PL", "CZ", "DK",
    "SE", "FI", "PT", "IE", "LU", "US", "GB", "CH", "IN", "CN",
}

EU_COUNTRY_CODES = {
    "DE", "FR", "IT", "ES", "NL", "BE", "AT", "PL", "CZ", "DK",
    "SE", "FI", "PT", "IE", "LU",
}

VALID_UNITS_OF_MEASURE = {"KG", "G", "L", "ML", "EA", "M", "CM", "PAL", "BOX"}

# German VAT ID format: "DE" + 9 digits. Simplified but real regex shape —
# other EU countries have different lengths/formats, out of scope here
# (documented in "What this doesn't demonstrate" in the README).
_VAT_ID_PATTERN = re.compile(r"^[A-Z]{2}[0-9A-Z]{2,12}$")


@dataclass(frozen=True)
class RuleViolation:
    rule_id: str
    field: str
    message: str
    severity: str  # "error" (blocks approval) or "warning" (flagged, not blocking)


# --- Customer rules -----------------------------------------------------

def rule_customer_country_code_valid(record: CustomerRecord) -> RuleViolation | None:
    if record.country_code not in VALID_ISO_COUNTRY_CODES:
        return RuleViolation(
            "CUST-001", "country_code",
            f"Unknown or unsupported country code '{record.country_code}'",
            "error",
        )
    return None


def rule_customer_eu_requires_vat_id(record: CustomerRecord) -> RuleViolation | None:
    """EU customers must have a VAT ID on file — a real, common master-data
    governance rule (intra-EU B2B transactions require a valid VAT ID for
    correct tax treatment)."""
    if record.country_code in EU_COUNTRY_CODES and not record.vat_id:
        return RuleViolation(
            "CUST-002", "vat_id",
            f"Customer in EU country '{record.country_code}' has no VAT ID on file",
            "error",
        )
    return None


def rule_customer_vat_id_format(record: CustomerRecord) -> RuleViolation | None:
    if record.vat_id and not _VAT_ID_PATTERN.match(record.vat_id):
        return RuleViolation(
            "CUST-003", "vat_id",
            f"VAT ID '{record.vat_id}' does not match the expected format (2 letters + alphanumeric)",
            "error",
        )
    return None


def rule_customer_postal_code_present(record: CustomerRecord) -> RuleViolation | None:
    if not record.postal_code or not record.postal_code.strip():
        return RuleViolation(
            "CUST-004", "postal_code", "Postal code is missing", "warning",
        )
    return None


CUSTOMER_RULES = [
    rule_customer_country_code_valid,
    rule_customer_eu_requires_vat_id,
    rule_customer_vat_id_format,
    rule_customer_postal_code_present,
]


# --- Vendor rules ---------------------------------------------------------

def rule_vendor_country_code_valid(record: VendorRecord) -> RuleViolation | None:
    if record.country_code not in VALID_ISO_COUNTRY_CODES:
        return RuleViolation(
            "VEND-001", "country_code",
            f"Unknown or unsupported country code '{record.country_code}'",
            "error",
        )
    return None


def rule_vendor_eu_requires_vat_id(record: VendorRecord) -> RuleViolation | None:
    if record.country_code in EU_COUNTRY_CODES and not record.vat_id:
        return RuleViolation(
            "VEND-002", "vat_id",
            f"Vendor in EU country '{record.country_code}' has no VAT ID on file",
            "error",
        )
    return None


def rule_vendor_payment_terms_reasonable(record: VendorRecord) -> RuleViolation | None:
    """Payment terms outside 0-120 days are flagged for review, not
    auto-rejected — unusual but not necessarily wrong (e.g. a strategic
    long-term supplier agreement), so this is a warning, not an error."""
    if record.payment_terms_days < 0 or record.payment_terms_days > 120:
        return RuleViolation(
            "VEND-003", "payment_terms_days",
            f"Payment terms of {record.payment_terms_days} days is outside the typical 0-120 day range",
            "warning",
        )
    return None


VENDOR_RULES = [
    rule_vendor_country_code_valid,
    rule_vendor_eu_requires_vat_id,
    rule_vendor_payment_terms_reasonable,
]


# --- Material rules ---------------------------------------------------------

def rule_material_unit_of_measure_valid(record: MaterialRecord) -> RuleViolation | None:
    if record.base_unit_of_measure not in VALID_UNITS_OF_MEASURE:
        return RuleViolation(
            "MAT-001", "base_unit_of_measure",
            f"Unit of measure '{record.base_unit_of_measure}' is not in the approved list",
            "error",
        )
    return None


def rule_material_price_not_negative(record: MaterialRecord) -> RuleViolation | None:
    if record.standard_price_eur is not None and record.standard_price_eur < 0:
        return RuleViolation(
            "MAT-002", "standard_price_eur",
            f"Standard price {record.standard_price_eur} is negative",
            "error",
        )
    return None


def rule_material_description_not_empty(record: MaterialRecord) -> RuleViolation | None:
    if not record.description or not record.description.strip():
        return RuleViolation(
            "MAT-003", "description", "Material description is missing", "error",
        )
    return None


MATERIAL_RULES = [
    rule_material_unit_of_measure_valid,
    rule_material_price_not_negative,
    rule_material_description_not_empty,
]


def validate_customer(record: CustomerRecord) -> list[RuleViolation]:
    return [v for rule in CUSTOMER_RULES if (v := rule(record)) is not None]


def validate_vendor(record: VendorRecord) -> list[RuleViolation]:
    return [v for rule in VENDOR_RULES if (v := rule(record)) is not None]


def validate_material(record: MaterialRecord) -> list[RuleViolation]:
    return [v for rule in MATERIAL_RULES if (v := rule(record)) is not None]
