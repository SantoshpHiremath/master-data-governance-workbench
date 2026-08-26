from src.records import CustomerRecord, VendorRecord, MaterialRecord
from src.business_rules import validate_customer, validate_vendor, validate_material


def make_customer(**overrides):
    defaults = dict(
        customer_id="C1", name="Test GmbH", country_code="DE", vat_id="DE123456789",
        street="Str 1", city="Berlin", postal_code="10115",
    )
    defaults.update(overrides)
    return CustomerRecord(**defaults)


def make_vendor(**overrides):
    defaults = dict(
        vendor_id="V1", name="Test Vendor", country_code="DE", vat_id="DE123456789",
        street="Str 1", city="Berlin", postal_code="10115", payment_terms_days=30,
    )
    defaults.update(overrides)
    return VendorRecord(**defaults)


def make_material(**overrides):
    defaults = dict(
        material_id="M1", description="Widget", material_group="RAW-METAL",
        base_unit_of_measure="EA", standard_price_eur=1.0,
    )
    defaults.update(overrides)
    return MaterialRecord(**defaults)


class TestCustomerRules:
    def test_clean_customer_passes_with_no_violations(self):
        assert validate_customer(make_customer()) == []

    def test_unknown_country_code_flagged(self):
        violations = validate_customer(make_customer(country_code="ZZ"))
        assert any(v.rule_id == "CUST-001" for v in violations)

    def test_eu_customer_without_vat_id_flagged(self):
        violations = validate_customer(make_customer(country_code="DE", vat_id=None))
        assert any(v.rule_id == "CUST-002" and v.severity == "error" for v in violations)

    def test_non_eu_customer_without_vat_id_not_flagged(self):
        violations = validate_customer(make_customer(country_code="IN", vat_id=None))
        assert not any(v.rule_id == "CUST-002" for v in violations)

    def test_malformed_vat_id_flagged(self):
        violations = validate_customer(make_customer(vat_id="not-a-vat-id!!"))
        assert any(v.rule_id == "CUST-003" for v in violations)

    def test_missing_postal_code_is_warning_not_error(self):
        violations = validate_customer(make_customer(postal_code=""))
        matched = [v for v in violations if v.rule_id == "CUST-004"]
        assert len(matched) == 1
        assert matched[0].severity == "warning"

    def test_multiple_violations_all_collected_not_just_first(self):
        # Bad country code AND missing postal code -> both should appear.
        violations = validate_customer(make_customer(country_code="ZZ", postal_code=""))
        rule_ids = {v.rule_id for v in violations}
        assert "CUST-001" in rule_ids
        assert "CUST-004" in rule_ids


class TestVendorRules:
    def test_clean_vendor_passes(self):
        assert validate_vendor(make_vendor()) == []

    def test_eu_vendor_without_vat_id_flagged(self):
        violations = validate_vendor(make_vendor(country_code="FR", vat_id=None))
        assert any(v.rule_id == "VEND-002" for v in violations)

    def test_payment_terms_out_of_range_flagged_as_warning(self):
        violations = validate_vendor(make_vendor(payment_terms_days=180))
        matched = [v for v in violations if v.rule_id == "VEND-003"]
        assert len(matched) == 1
        assert matched[0].severity == "warning"

    def test_negative_payment_terms_flagged(self):
        violations = validate_vendor(make_vendor(payment_terms_days=-5))
        assert any(v.rule_id == "VEND-003" for v in violations)

    def test_payment_terms_at_boundary_not_flagged(self):
        violations = validate_vendor(make_vendor(payment_terms_days=120))
        assert not any(v.rule_id == "VEND-003" for v in violations)


class TestMaterialRules:
    def test_clean_material_passes(self):
        assert validate_material(make_material()) == []

    def test_invalid_unit_of_measure_flagged(self):
        violations = validate_material(make_material(base_unit_of_measure="BUSHEL"))
        assert any(v.rule_id == "MAT-001" for v in violations)

    def test_negative_price_flagged(self):
        violations = validate_material(make_material(standard_price_eur=-1.0))
        assert any(v.rule_id == "MAT-002" for v in violations)

    def test_none_price_not_flagged_as_negative(self):
        # None means "not yet priced," which is a distinct, legitimate state
        # from a negative price — must not be misclassified as an error.
        violations = validate_material(make_material(standard_price_eur=None))
        assert not any(v.rule_id == "MAT-002" for v in violations)

    def test_empty_description_flagged(self):
        violations = validate_material(make_material(description="   "))
        assert any(v.rule_id == "MAT-003" for v in violations)
