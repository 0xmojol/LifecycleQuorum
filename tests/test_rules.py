import importlib.util
import json
import pathlib
import sys
import types
import unittest


class PublicDecorators:
    def __getattr__(self, _name):
        return lambda function: function


class FakeGL:
    Contract = object
    public = PublicDecorators()
    vm = types.SimpleNamespace(Return=type("Return", (), {}))


fake_genlayer = types.ModuleType("genlayer")
fake_genlayer.gl = FakeGL()
fake_genlayer.TreeMap = dict
sys.modules.setdefault("genlayer", fake_genlayer)

CONTRACT_PATH = pathlib.Path(__file__).parents[1] / "contracts" / "lifecycle_quorum.py"
spec = importlib.util.spec_from_file_location("lifecycle_quorum_contract", CONTRACT_PATH)
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def make_sources(major, start, lts, maintenance, end, registry_maintenance=None):
    official = {
        "v" + major: {
            "start": start,
            "lts": lts or None,
            "maintenance": maintenance or None,
            "end": end,
        }
    }
    registry = [
        {
            "cycle": major,
            "releaseDate": start,
            "lts": lts or False,
            "support": (
                registry_maintenance
                if registry_maintenance is not None
                else (maintenance or False)
            ),
            "eol": end,
        }
    ]
    return json.dumps(official), json.dumps(registry)


class LifecycleRules(unittest.TestCase):
    def test_current_before_lts(self):
        official, registry = make_sources(
            "26", "2026-05-05", "2026-10-28", "2027-10-20",
            "2029-04-30", "2027-10-20"
        )
        result = contract._canonical_record(
            "26", "2026-10-21", official, registry
        )
        self.assertEqual(result["state"], "CURRENT")
        self.assertEqual(result["reason_code"], "SOURCES_CORROBORATED")

    def test_maintenance_lts_is_derived_from_agreed_dates(self):
        official, registry = make_sources(
            "24", "2025-05-06", "2025-10-28", "2026-10-20",
            "2028-04-30"
        )
        result = contract._canonical_record(
            "24", "2026-10-21", official, registry
        )
        self.assertEqual(result["state"], "MAINTENANCE_LTS")

    def test_end_of_life_boundary(self):
        official, registry = make_sources(
            "20", "2023-04-18", "2023-10-24", "2024-10-22",
            "2026-04-30"
        )
        result = contract._canonical_record(
            "20", "2026-10-21", official, registry
        )
        self.assertEqual(result["state"], "END_OF_LIFE")

    def test_seven_day_support_boundary_difference_is_equivalent(self):
        official, registry = make_sources(
            "26", "2026-05-05", "2026-10-28", "2027-10-20",
            "2029-04-30", "2027-10-27"
        )
        result = contract._canonical_record(
            "26", "2026-10-21", official, registry
        )
        self.assertEqual(result["state"], "CURRENT")
        self.assertEqual(result["registry_support"], "2027-10-27")

    def test_difference_over_seven_days_is_a_conflict(self):
        official, registry = make_sources(
            "26", "2026-05-05", "2026-10-28", "2027-10-20",
            "2029-04-30", "2027-11-10"
        )
        result = contract._canonical_record(
            "26", "2026-10-21", official, registry
        )
        self.assertEqual(result["state"], "SOURCE_CONFLICT")
        self.assertEqual(result["reason_code"], "LIFECYCLE_FIELDS_DISAGREE")

    def test_missing_cycle_is_unresolved(self):
        result = contract._canonical_record("99", "2026-10-21", "{}", "[]")
        self.assertEqual(result["state"], "UNRESOLVED")

    def test_malformed_source_is_unresolved(self):
        result = contract._canonical_record("24", "2026-10-21", "not-json", "[]")
        self.assertEqual(result["state"], "UNRESOLVED")
        self.assertEqual(result["reason_code"], "SOURCE_PARSE_ERROR")

    def test_dates_are_derived_without_float_or_local_clock(self):
        self.assertEqual(
            contract.__derive_phase(
                "2026-10-21",
                "2026-05-05",
                "2026-10-28",
                "2027-10-20",
                "2029-04-30",
            ),
            "CURRENT",
        )
        self.assertEqual(
            contract._derive_phase(
                "2027-10-20",
                "2026-05-05",
                "2026-10-28",
                "2027-10-20",
                "2029-04-30",
            ),
            "MAINTENANCE_LTS",
        )


if __name__ == "__main__":
    unittest.main()
