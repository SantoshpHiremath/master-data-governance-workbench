# Master Data Governance Workbench

A real, tested Python project modeling the daily workflow of a master
data governance role — built to close a specific gap for Siemens
Energy's "Working Student Master Data Governance" posting: hands-on
evidence of the exact tasks it names (cleansing/validating customer,
vendor, and material records; running duplicate/inconsistency reports;
executing data-maintenance requests against documented business rules
and service levels; producing an audit trail), in a real, runnable
system rather than a description of the concept.

## What this is (read before citing anywhere)

**There is no real SAP, ERP system, or Siemens Energy data here.** This
project does not connect to SAP, does not use Power Query (which
requires Windows Excel/Power BI Desktop, unavailable in this build
environment — see `powerquery-sap-reporting` for that specific
disclosure), and the seed dataset (`src/seed_data.py`) is a small,
hand-built set of placeholder companies and materials, not real records
from any company. I have no real SAP or ERP-system experience.

What's built here is the underlying governance logic a real master-data
role runs on top of an ERP system: business-rule validation, duplicate
detection, a change-request state machine, service-level tracking, and
an audit trail — implemented and tested against genuinely messy
synthetic data, on a system I could construct, break, and verify myself.

## What this models

- **`src/records.py`** — the three master data object types the posting
  names explicitly: customer, vendor, material, with the fields real
  master-data quality work actually cares about (VAT ID, address,
  payment terms, unit of measure), not a generic id/name toy model.
- **`src/business_rules.py`** — the posting's "help document data
  standards, business rules, and process workflows" task: each rule is a
  small, named, independently testable function (e.g. "EU customers
  require a VAT ID on file"), which IS the documentation — a governance
  reviewer could read this file top to bottom as the current rule set,
  rather than a separate document that can drift out of sync with the
  code. Rules are error (blocking) or warning (flagged, not blocking) —
  a real governance process needs both.
- **`src/duplicate_detection.py`** — the posting's "run predefined
  reports to identify duplicates" task, done with actual normalized
  matching (case-folding, umlaut transliteration, legal-suffix
  stripping) rather than naive exact-string comparison, since real
  master-data duplicates are almost never identical strings. Two
  independent matching passes (normalized name+postal-code, and exact
  VAT ID) catch two different real failure modes — a same-company-typed-
  differently duplicate, and a same-legal-entity-different-trading-name
  duplicate that name matching alone would miss.
- **`src/change_requests.py`** — the posting's "execute routine data
  maintenance requests... according to established procedures and
  service levels" and audit-trail tasks: a `ChangeRequest` goes through
  an explicit SUBMITTED → VALIDATED → APPLIED (or REJECTED) state
  machine, validated against the business rules BEFORE touching the
  master dataset, with every transition producing an audit-trail entry —
  not reconstructed after the fact from the final data state, which
  would lose the "why." Includes SLA breach detection (`check_sla`).
- **`src/reports.py`** — assembles the data-quality report a data
  steward would pull up before a governance meeting: violations and
  duplicates across all three object types in one place.
- **`src/seed_data.py`** — a small, deliberately messy starting dataset
  with known, hand-built issues (a customer duplicated under a
  transliterated/re-capitalized name, a customer duplicated under a
  different trading name sharing one VAT ID, a material duplicated under
  two IDs, a vendor with out-of-range payment terms) — so the reports
  above have real, known findings to surface, not a synthetically-clean
  dataset that would prove nothing.

## A real bug found and fixed during development

The first version of the test suite used placeholder VAT IDs like
`"DE1"` in fixtures unrelated to VAT-ID testing (e.g. testing that an
UPDATE replaces rather than appends a record). This tripped the VAT-ID-
format business rule unintentionally, since `"DE1"` doesn't match the
expected format (2 letters + at least 2 alphanumeric characters) — five
tests failed not because the governance logic was wrong, but because the
fixtures accidentally exercised a rule the tests weren't about. This is
disclosed here because it's a genuine reminder that realistic-looking
placeholder data still needs to pass real validation, and because the
failure correctly proved the VAT-ID format rule works — it just needed
fixtures that didn't collide with it. Fixed by using a realistic,
valid-format VAT ID (`"DE123456789"`) throughout the change-request
tests, verified by rerunning the full suite (52/52 passing after the fix).

## Verification

52 tests (`pytest tests/ -v`), including:

- Business-rule tests for every rule (customer, vendor, material),
  covering both the positive case (rule doesn't fire on a clean record)
  and the negative case, plus a check that multiple violations on one
  record are all collected, not just the first.
- Duplicate-detection tests proving the normalization actually catches
  real near-duplicates (umlaut transliteration, legal-suffix variance,
  capitalization) while NOT producing false positives (two genuinely
  different companies, or two different records that both happen to
  have no VAT ID, must not be grouped together).
- Change-request lifecycle tests covering the full state machine,
  including that a request with a blocking violation is rejected AND
  never touches the master dataset, that an UPDATE replaces rather than
  appends, and that CREATE/UPDATE correctly reject invalid preconditions
  (ID already exists / doesn't exist).
- Audit-trail tests confirming every state transition produces an entry,
  a rejected request's trail stops at "rejected" rather than showing a
  phantom "applied," and the returned log is a snapshot, not a live
  reference that would appear to retroactively grow.
- Service-level tests: a request within SLA doesn't raise, one past SLA
  does, and — importantly — a request that reached a terminal state
  (APPLIED or REJECTED) never breaches SLA regardless of how old it is,
  since the SLA is about resolution time, not total lifespan.
- Report tests confirming clean records are excluded from the violations
  output (so the report stays readable), and that warning-only records
  are surfaced but not counted in the "records with errors" total.

## Running it

```bash
pip install -r requirements.txt
python3 run_demo.py         # data quality report + change-request walkthrough + audit trail
pytest tests/ -v             # 52 tests
```

## What this doesn't demonstrate

This project doesn't connect to SAP, any real ERP system, or Power
Query, doesn't use real company data, and doesn't reproduce SAP's actual
master-data object model in full (real SAP customer/vendor/material
master records have many more fields and country-specific validation
rules than modeled here — VAT ID format checking here is simplified to
one general pattern, not each EU country's actual specific format). It
demonstrates the underlying governance logic — business-rule
documentation, duplicate detection on realistically messy data, a
request/approval/audit workflow, and service-level tracking — built and
verified on a system I could construct myself, closing a specific,
honestly-scoped gap rather than claiming real SAP experience I don't have.
