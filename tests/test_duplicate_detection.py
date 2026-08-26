from src.records import CustomerRecord, VendorRecord, MaterialRecord
from src.duplicate_detection import (
    normalize_name, normalize_postal_code,
    find_customer_duplicates, find_vendor_duplicates, find_material_duplicates,
)


class TestNormalizeName:
    def test_case_folds(self):
        assert normalize_name("MUELLER GMBH") == normalize_name("mueller gmbh")

    def test_transliterates_umlauts(self):
        assert normalize_name("Müller GmbH") == normalize_name("Mueller GmbH")

    def test_strips_legal_suffix_gmbh(self):
        assert normalize_name("Test GmbH") == "test"

    def test_strips_legal_suffix_gmbh_and_co_kg(self):
        assert normalize_name("Test GmbH & Co KG") == "test"

    def test_collapses_irregular_whitespace(self):
        assert normalize_name("Test   Company") == normalize_name("Test Company")

    def test_names_without_suffix_untouched_besides_case(self):
        assert normalize_name("Acme") == "acme"

    def test_different_companies_do_not_accidentally_normalize_to_the_same_key(self):
        assert normalize_name("Nordwind Logistik AG") != normalize_name("Alpine Components SA")


class TestNormalizePostalCode:
    def test_strips_whitespace_and_uppercases(self):
        assert normalize_postal_code(" m1 2ab ") == "M12AB"


class TestFindCustomerDuplicates:
    def test_finds_near_duplicate_by_normalized_name_and_postal_code(self):
        customers = [
            CustomerRecord("C1", "Müller GmbH", "DE", "DE111", "Str 1", "München", "80331"),
            CustomerRecord("C2", "MUELLER", "DE", None, "Str 1", "München", "80331"),
        ]
        groups = find_customer_duplicates(customers)
        assert len(groups) == 1
        assert set(groups[0].record_ids) == {"C1", "C2"}
        assert groups[0].match_basis == "name+postal_code"

    def test_finds_duplicate_by_shared_vat_id_even_with_different_names(self):
        customers = [
            CustomerRecord("C1", "Alpine Components SA", "FR", "FR999", "Str 1", "Lyon", "69001"),
            CustomerRecord("C2", "Alpine Export Division", "FR", "FR999", "Different St", "Paris", "75001"),
        ]
        groups = find_customer_duplicates(customers)
        assert len(groups) == 1
        assert groups[0].match_basis == "vat_id"

    def test_does_not_group_unrelated_customers_with_no_vat_id(self):
        # Two different customers, both with vat_id=None — must NOT be
        # grouped together just because they share the value None.
        customers = [
            CustomerRecord("C1", "Company One", "IN", None, "Str 1", "Delhi", "110001"),
            CustomerRecord("C2", "Company Two", "IN", None, "Str 2", "Mumbai", "400001"),
        ]
        assert find_customer_duplicates(customers) == []

    def test_no_false_positive_for_genuinely_different_customers(self):
        customers = [
            CustomerRecord("C1", "Nordwind Logistik AG", "DE", "DE1", "Str 1", "Hamburg", "20457"),
            CustomerRecord("C2", "Baltic Freight Ltd", "IN", "IN2", "Str 2", "Bengaluru", "560001"),
        ]
        assert find_customer_duplicates(customers) == []

    def test_three_way_duplicate_grouped_together_not_as_separate_pairs(self):
        customers = [
            CustomerRecord("C1", "Test GmbH", "DE", None, "Str 1", "Berlin", "10115"),
            CustomerRecord("C2", "TEST GMBH", "DE", None, "Str 1", "Berlin", "10115"),
            CustomerRecord("C3", "test", "DE", None, "Str 1", "Berlin", "10115"),
        ]
        groups = find_customer_duplicates(customers)
        assert len(groups) == 1
        assert set(groups[0].record_ids) == {"C1", "C2", "C3"}


class TestFindVendorDuplicates:
    def test_finds_vendor_near_duplicate(self):
        vendors = [
            VendorRecord("V1", "Stahlwerk Nord GmbH", "DE", "DE1", "Str 1", "Essen", "45127", 30),
            VendorRecord("V2", "STAHLWERK NORD", "DE", None, "Str 1", "Essen", "45127", 60),
        ]
        groups = find_vendor_duplicates(vendors)
        assert len(groups) == 1
        assert set(groups[0].record_ids) == {"V1", "V2"}


class TestFindMaterialDuplicates:
    def test_finds_material_duplicate_by_description_group_and_uom(self):
        materials = [
            MaterialRecord("M1", "Bolt M6x20 Steel", "RAW-METAL", "EA", 0.08),
            MaterialRecord("M2", "Bolt M6x20 Steel", "RAW-METAL", "EA", 0.09),
        ]
        groups = find_material_duplicates(materials)
        assert len(groups) == 1
        assert set(groups[0].record_ids) == {"M1", "M2"}

    def test_same_description_different_group_not_flagged(self):
        # Same short description text can legitimately describe two
        # different real materials if the group differs (e.g. a
        # different bolt used in a different product line).
        materials = [
            MaterialRecord("M1", "Bolt M6x20 Steel", "RAW-METAL", "EA", 0.08),
            MaterialRecord("M2", "Bolt M6x20 Steel", "SPARE-PART", "EA", 0.50),
        ]
        assert find_material_duplicates(materials) == []
