import unittest

from detectors import (
    CURATED_CHEMICAL_SYNONYMS,
    curated_fragmentation_clusters,
    has_duration_temperature_confusion,
    mechanical_fragmentation_clusters,
    quantity_is_empty,
)


class QuantityIsEmptyTests(unittest.TestCase):
    def test_none_is_empty(self):
        self.assertTrue(quantity_is_empty(None))

    def test_all_null_fields_is_empty(self):
        self.assertTrue(quantity_is_empty({"value": None, "unit": None, "raw_text": None}))

    def test_unit_only_is_not_empty(self):
        # Real edge case found in response_Fischer_Tropsch_process.json.
        self.assertFalse(quantity_is_empty({"value": None, "unit": "atm", "raw_text": None}))

    def test_populated_is_not_empty(self):
        self.assertFalse(quantity_is_empty({"value": 300.0, "unit": "degC", "raw_text": None}))


class DurationTemperatureConfusionTests(unittest.TestCase):
    def test_celsius_in_duration_flagged(self):
        record = {"has_duration": "55 degC", "has_temperature": None}
        result = has_duration_temperature_confusion(record)
        self.assertIsNotNone(result)
        self.assertEqual(result["has_duration_value"], "55 degC")

    def test_degree_sign_variant_flagged(self):
        record = {"has_duration": "24-70 °C", "has_temperature": None}
        self.assertIsNotNone(has_duration_temperature_confusion(record))

    def test_plain_duration_not_flagged(self):
        record = {"has_duration": "2 h", "has_temperature": None}
        self.assertIsNone(has_duration_temperature_confusion(record))

    def test_plain_hours_duration_not_flagged(self):
        record = {"has_duration": "50 hours", "has_temperature": None}
        self.assertIsNone(has_duration_temperature_confusion(record))

    def test_missing_duration_not_flagged(self):
        self.assertIsNone(has_duration_temperature_confusion({"has_duration": None, "has_temperature": None}))

    def test_not_flagged_when_temperature_also_populated(self):
        # Both fields populated is redundancy, not the confusion pattern.
        record = {
            "has_duration": "80 degC",
            "has_temperature": {"value": 80.0, "unit": "degC", "raw_text": None},
        }
        self.assertIsNone(has_duration_temperature_confusion(record))


class MechanicalFragmentationTests(unittest.TestCase):
    def test_formula_and_parenthetical_variants_cluster(self):
        labels = ["dinitrogen (N2)", "N 2", "N2", "hydrogen"]
        clusters = mechanical_fragmentation_clusters(labels)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(set(clusters[0]), {"dinitrogen (N2)", "N 2", "N2"})

    def test_bare_name_and_bare_formula_bridge_via_parenthetical_label(self):
        labels = ["SO2", "sulfur dioxide", "sulfur dioxide (SO2)"]
        clusters = mechanical_fragmentation_clusters(labels)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(set(clusters[0]), set(labels))

    def test_no_space_before_paren_does_not_split(self):
        # "nitrogen oxides(NOx)" has no space before "(" -> must not bridge
        # to the N2 family via a spurious "nox"/"oxides" key.
        labels = ["dinitrogen (N2)", "N 2", "N2", "nitrogen oxides(NOx)"]
        clusters = mechanical_fragmentation_clusters(labels)
        self.assertEqual(len(clusters), 1)
        self.assertNotIn("nitrogen oxides(NOx)", clusters[0])

    def test_urea_does_not_merge_with_carbon_dioxide(self):
        # Regression: mid-token paren in a real formula ("CO(NH2)2", urea)
        # must not split and falsely merge with CO2/CO 2.
        labels = ["CO(NH2)2", "CO2", "CO 2"]
        clusters = mechanical_fragmentation_clusters(labels)
        self.assertEqual(len(clusters), 1)
        self.assertNotIn("CO(NH2)2", clusters[0])
        self.assertEqual(set(clusters[0]), {"CO2", "CO 2"})

    def test_unrelated_nitrogen_oxides_stay_distinct_from_each_other(self):
        labels = ["NO", "NO2", "N2O", "NOx"]
        self.assertEqual(mechanical_fragmentation_clusters(labels), [])

    def test_singleton_labels_produce_no_clusters(self):
        self.assertEqual(mechanical_fragmentation_clusters(["iron", "platinum", "water"]), [])


class CuratedFragmentationTests(unittest.TestCase):
    def test_curated_layer_folds_plain_name_into_formula_cluster(self):
        labels = ["nitrogen", "N2", "N 2", "dinitrogen (N2)"]
        mechanical = mechanical_fragmentation_clusters(labels)
        # Without the synonym layer, "nitrogen" stays separate.
        self.assertTrue(all("nitrogen" not in cluster or len(cluster) < 4 for cluster in mechanical))

        curated = curated_fragmentation_clusters(labels, CURATED_CHEMICAL_SYNONYMS)
        self.assertEqual(len(curated), 1)
        self.assertEqual(set(curated[0]), set(labels))

    def test_hydrogen_gas_is_not_folded_in(self):
        # "hydrogen gas" is deliberately absent from CURATED_CHEMICAL_SYNONYMS
        # -- it must stay out of the hydrogen cluster.
        labels = ["hydrogen", "H2", "H 2", "hydrogen gas"]
        curated = curated_fragmentation_clusters(labels, CURATED_CHEMICAL_SYNONYMS)
        self.assertEqual(len(curated), 1)
        self.assertEqual(set(curated[0]), {"hydrogen", "H2", "H 2"})


if __name__ == "__main__":
    unittest.main()
