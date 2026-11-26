"""Unit assertions for normalization and chronology in the B01 audit."""

import unittest
from team_tools.audit_data import field_semantics, verify_normalization, verify_chronology


class DataAuditTests(unittest.TestCase):
    def test_temperature_conversion_uses_response_measurement_key(self):
        constants = {"zone_air_temperature_sensor": {"sample_mean": 295., "sample_std": 5.}}
        result = verify_normalization("zone_air_temperature_sensor", -0.2, 294., constants)
        self.assertAlmostEqual(result["reconstructed_native"], 294.)
        identity = verify_normalization("ahu_1_supply_air_temperature_sensor", 298., 298., constants)
        self.assertEqual(identity["normalization"], "identity")

    def test_wrong_unit_or_normalization_fails(self):
        with self.assertRaises(ValueError):
            verify_normalization("zone_air_temperature_sensor", 21., 294., {"zone_air_temperature_sensor": {"sample_mean": 295., "sample_std": 5.}})

    def test_pressure_units_depend_on_device(self):
        self.assertEqual(field_semantics("hws", "differential_pressure_setpoint")[0], "bar")
        self.assertEqual(field_semantics("ahs", "ahu_1_supply_air_static_pressure_sensor")[0], "Pa")

    def test_unknown_field_is_not_silently_assigned_a_unit(self):
        with self.assertRaises(ValueError):
            field_semantics("new_device", "unknown_sensor")

    def test_transition_must_advance_exactly_one_interval(self):
        verify_chronology("2026-01-01T00:00:00+00:00", "2026-01-01T00:05:00+00:00", 300.)
        with self.assertRaises(ValueError):
            verify_chronology("2026-01-01T00:00:00+00:00", "2026-01-01T00:10:00+00:00", 300.)


if __name__ == "__main__":
    unittest.main()
