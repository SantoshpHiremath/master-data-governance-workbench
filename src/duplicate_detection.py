"""
duplicate_detection.py
-----------------------
The posting's "support data quality initiatives by running predefined
reports to identify duplicates, inconsistencies, or incomplete data"
task, applied to customer and vendor records.

Real master-data duplicates are rarely exact-string matches — "Muller
GmbH" vs. "Müller GmbH" vs. "MUELLER GMBH" are very likely the same
company, entered by three different people over the years. This module
does NORMALIZED matching (case-folding, umlaut transliteration, legal-
suffix stripping, whitespace collapsing) rather than naive `==`
comparison, which is the actual skill real master-data dedup work
requires — an exact-match check would miss almost every real duplicate.
"""

from dataclasses import dataclass

from .records import CustomerRecord, VendorRecord

_UMLAUT_MAP = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

_LEGAL_SUFFIXES = [
    " gmbh & co kg", " gmbh and co kg", " gmbh", " ag", " kg", " ohg",
    " e.v.", " ev", " inc", " inc.", " llc", " ltd", " ltd.", " s.a.",
    " s.a", " s.r.l.", " sarl", " bv", " nv",
]


def normalize_name(name: str) -> str:
    """Case-fold, transliterate umlauts, strip common legal-entity
    suffixes, and collapse whitespace — the normalization a real
    duplicate-detection report needs to catch near-matches, not just
    exact ones."""
    n = name.lower().strip()
    n = n.translate(_UMLAUT_MAP)
    n = " ".join(n.split())  # collapse repeated/irregular whitespace
    for suffix in _LEGAL_SUFFIXES:
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
            break  # only strip one suffix — "X GmbH & Co KG AG" is not a realistic case to chase further
    return n


def normalize_postal_code(postal_code: str) -> str:
    return "".join(postal_code.split()).upper()


@dataclass(frozen=True)
class DuplicateGroup:
    record_ids: tuple[str, ...]
    match_key: str
    match_basis: str  # "name+postal_code" or "vat_id"


def find_customer_duplicates(customers: list[CustomerRecord]) -> list[DuplicateGroup]:
    return _find_duplicates(
        customers,
        id_fn=lambda c: c.customer_id,
        name_fn=lambda c: c.name,
        postal_fn=lambda c: c.postal_code,
        vat_fn=lambda c: c.vat_id,
    )


def find_vendor_duplicates(vendors: list[VendorRecord]) -> list[DuplicateGroup]:
    return _find_duplicates(
        vendors,
        id_fn=lambda v: v.vendor_id,
        name_fn=lambda v: v.name,
        postal_fn=lambda v: v.postal_code,
        vat_fn=lambda v: v.vat_id,
    )


def _find_duplicates(records, id_fn, name_fn, postal_fn, vat_fn) -> list[DuplicateGroup]:
    """
    Two independent matching passes, since they catch different real
    failure modes:

    1. normalized-name + postal-code match — catches "same company,
       typed differently" (the common case: capitalization, umlaut
       transliteration, legal-suffix variance, extra whitespace).
    2. exact VAT ID match — catches "same legal entity, completely
       different name spelling" (e.g. a trading name vs. a legal name),
       which the name-based pass would miss entirely. A VAT ID is a
       strong, near-unique identifier when present, so even a single
       exact match on it is meaningful — unlike name matching, where
       real companies can legitimately share a name.
    """
    groups: list[DuplicateGroup] = []

    # Pass 1: normalized name + postal code
    by_name_postal: dict[tuple[str, str], list[str]] = {}
    for r in records:
        key = (normalize_name(name_fn(r)), normalize_postal_code(postal_fn(r)))
        by_name_postal.setdefault(key, []).append(id_fn(r))

    for (norm_name, norm_postal), ids in by_name_postal.items():
        if len(ids) > 1:
            groups.append(
                DuplicateGroup(
                    record_ids=tuple(sorted(ids)),
                    match_key=f"{norm_name} / {norm_postal}",
                    match_basis="name+postal_code",
                )
            )

    # Pass 2: exact VAT ID match (only for records that HAVE a VAT ID —
    # grouping on None would falsely group every VAT-less record together)
    by_vat: dict[str, list[str]] = {}
    for r in records:
        vat = vat_fn(r)
        if vat:
            by_vat.setdefault(vat, []).append(id_fn(r))

    already_grouped_ids = {rid for g in groups for rid in g.record_ids}
    for vat, ids in by_vat.items():
        if len(ids) > 1:
            # Skip if this exact set of IDs was already caught by pass 1,
            # to avoid reporting the same duplicate pair twice under two
            # different match_basis labels.
            if set(ids).issubset(already_grouped_ids) and any(
                set(ids) == set(g.record_ids) for g in groups
            ):
                continue
            groups.append(
                DuplicateGroup(
                    record_ids=tuple(sorted(ids)), match_key=vat, match_basis="vat_id",
                )
            )

    return groups


def find_material_duplicates(materials) -> list[DuplicateGroup]:
    """Materials are matched on normalized description + material group
    + unit of measure — a material's "name" (description) alone is a
    weaker signal than a customer/vendor name, since many genuinely
    different materials share a short description (e.g. "Bolt M6");
    group + UoM narrows it to a real duplicate candidate."""
    by_key: dict[tuple[str, str, str], list[str]] = {}
    for m in materials:
        key = (normalize_name(m.description), m.material_group, m.base_unit_of_measure)
        by_key.setdefault(key, []).append(m.material_id)

    return [
        DuplicateGroup(record_ids=tuple(sorted(ids)), match_key=f"{k[0]} / {k[1]} / {k[2]}", match_basis="description+group+uom")
        for k, ids in by_key.items()
        if len(ids) > 1
    ]
