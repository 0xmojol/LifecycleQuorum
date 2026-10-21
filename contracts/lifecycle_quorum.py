# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""LifecycleQuorum: consensus-checked Node.js release lifecycle attestations.

Two independently maintained public schedules are normalized and compared.
The contract never treats disagreement or missing fields as a supported status.
"""

from genlayer import *
import hashlib
import json
import typing

OFFICIAL_URL = "https://raw.githubusercontent.com/nodejs/Release/main/schedule.json"
REGISTRY_URL = "https://endoflife.date/api/nodejs.json"
MAX_HISTORY_PER_CYCLE = 20
ALLOWED_STATES = (
    "CURRENT",
    "ACTIVE_LTS",
    "MAINTENANCE_LTS",
    "END_OF_LIFE",
    "NOT_YET_RELEASED",
    "SOURCE_CONFLICT",
    "UNRESOLVED",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normal_date(value: typing.Any) -> str:
    """Return a valid ISO calendar date or empty string; reject booleans."""
    if not isinstance(value, str) or len(value) != 10:
        return ""
    if value[4] != "-" or value[7] != "-":
        return ""
    if not (value[:4].isdigit() and value[5:7].isdigit() and value[8:10].isdigit()):
        return ""
    year, month, day = int(value[:4]), int(value[5:7]), int(value[8:10])
    if year < 1 or month < 1 or month > 12:
        return ""
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if day < 1 or day > month_days[month - 1]:
        return ""
    return value


def _days_from_date(value: str) -> int:
    """Gregorian ordinal for a validated YYYY-MM-DD string, with integer math."""
    if not _normal_date(value):
        raise ValueError("invalid ISO date")
    year = int(value[0:4])
    month = int(value[5:7])
    day = int(value[8:10])
    if month < 1 or month > 12:
        raise ValueError("invalid month")
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if day < 1 or day > month_days[month - 1]:
        raise ValueError("invalid day")
    prior_year = year - 1
    ordinal = 365 * prior_year + prior_year // 4 - prior_year // 100 + prior_year // 400
    ordinal += sum(month_days[: month - 1]) + day
    return ordinal


def _within_day_tolerance(left: str, right: str, tolerance: int) -> bool:
    if not left or not right:
        return left == right
    try:
        return abs(_days_from_date(left) - _days_from_date(right)) <= tolerance
    except Exception:
        return False


def _derive_phase(as_of: str, start: str, lts: str, maintenance: str, end: str) -> str:
    """Derive a lifecycle phase only from agreed, canonical date fields."""
    if not _normal_date(as_of) or not start or not end:
        return "UNRESOLVED"
    if as_of < start:
        return "NOT_YET_RELEASED"
    if as_of >= end:
        return "END_OF_LIFE"
    if lts and as_of >= lts:
        if maintenance and as_of >= maintenance:
            return "MAINTENANCE_LTS"
        return "ACTIVE_LTS"
    return "CURRENT"


def _canonical_record(major: str, as_of: str, official_json: str, registry_json: str) -> dict:
    """Parse both sources and derive a canonical record without an LLM."""
    try:
        official = json.loads(official_json)
        registry = json.loads(registry_json)
        official_row = official.get("v" + major)
        registry_rows = registry if isinstance(registry, list) else []
        registry_row = None
        for row in registry_rows:
            if isinstance(row, dict) and str(row.get("cycle", "")) == major:
                registry_row = row
                break
        if not isinstance(official_row, dict) or not isinstance(registry_row, dict):
            return {
                "major": major,
                "state": "UNRESOLVED",
                "reason_code": "CYCLE_MISSING_FROM_SOURCE",
                "start": "",
                "lts": "",
                "maintenance": "",
                "registry_support": "",
                "end": "",
                "as_of": as_of,
            }

        start = _normal_date(official_row.get("start"))
        official_lts = _normal_date(official_row.get("lts"))
        maintenance = _normal_date(official_row.get("maintenance"))
        end = _normal_date(official_row.get("end"))

        registry_start = _normal_date(registry_row.get("releaseDate"))
        registry_lts = _normal_date(registry_row.get("lts"))
        registry_maintenance = _normal_date(registry_row.get("support"))
        registry_end = _normal_date(registry_row.get("eol"))

        valid = bool(start and end and registry_start and registry_end)
        # The community API's `support` boundary can be published up to one
        # week after the official schedule's maintenance transition. Treat only
        # that narrow, explicit interval as equivalent; all other fields are exact.
        agrees = (
            valid
            and start == registry_start
            and official_lts == registry_lts
            and _within_day_tolerance(maintenance, registry_maintenance, 7)
            and end == registry_end
        )
        if not agrees:
            state = "SOURCE_CONFLICT" if valid else "UNRESOLVED"
            return {
                "major": major,
                "state": state,
                "reason_code": "LIFECYCLE_FIELDS_DISAGREE" if valid else "REQUIRED_DATE_MISSING",
                "start": start,
                "lts": official_lts,
                "maintenance": maintenance,
                "registry_support": registry_maintenance,
                "end": end,
                "as_of": as_of,
            }

        state = _derive_phase(as_of, start, official_lts, maintenance, end)
        return {
            "major": major,
            "state": state,
            "reason_code": "SOURCES_CORROBORATED",
            "start": start,
            "lts": official_lts,
            "maintenance": maintenance,
            "registry_support": registry_maintenance,
            "end": end,
            "as_of": as_of,
        }
    except Exception:
        return {
            "major": major,
            "state": "UNRESOLVED",
            "reason_code": "SOURCE_PARSE_ERROR",
            "start": "",
            "lts": "",
            "maintenance": "",
            "registry_support": "",
            "end": "",
            "as_of": as_of,
        }


class LifecycleQuorum(gl.Contract):
    observations: TreeMap[str, str]
    counts: TreeMap[str, str]

    def __init__(self):
        self.observations = TreeMap()
        self.counts = TreeMap()

    @gl.public.write
    def assess_cycle(self, major: str) -> str:
        """Fetch and independently corroborate one Node.js major release cycle."""
        major = str(major).strip()
        assert major.isdigit() and 1 <= int(major) <= 99, "major must be 1..99"
        count = int(self.counts.get(major, "0"))
        assert count < MAX_HISTORY_PER_CYCLE, "History limit reached for this cycle"
        as_of = str(gl.message_raw["datetime"])[:10]

        def observe() -> dict:
            official_response = gl.nondet.web.get(OFFICIAL_URL)
            registry_response = gl.nondet.web.get(REGISTRY_URL)
            official_text = official_response.body.decode("utf-8")
            registry_text = registry_response.body.decode("utf-8")
            record = _canonical_record(major, as_of, official_text, registry_text)
            record["official_sha256"] = _sha256(official_text)
            record["registry_sha256"] = _sha256(registry_text)
            return record

        def leader_fn() -> dict:
            return observe()

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            proposed = leader_result.calldata
            if not isinstance(proposed, dict) or proposed.get("state") not in ALLOWED_STATES:
                return False
            independent = observe()
            # Validate the complete normalized record, both source bindings,
            # and the deterministic state derived from this transaction date.
            return independent == proposed

        agreed = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        observation = dict(agreed)
        observation["sequence"] = str(count + 1)
        observation["assessed_at"] = str(gl.message_raw["datetime"])
        key = major + ":" + str(count + 1)
        self.observations[key] = json.dumps(observation, sort_keys=True)
        self.counts[major] = str(count + 1)
        return key

    @gl.public.view
    def get_latest(self, major: str) -> str:
        major = str(major)
        count = int(self.counts.get(major, "0"))
        if count == 0:
            return json.dumps(
                {"major": major, "state": "UNRESOLVED", "reason_code": "NO_OBSERVATION"},
                sort_keys=True,
            )
        return str(self.observations[major + ":" + str(count)])

    @gl.public.view
    def get_observation(self, major: str, sequence: str) -> str:
        key = str(major) + ":" + str(sequence)
        assert key in self.observations, "Unknown observation"
        return str(self.observations[key])

    @gl.public.view
    def status_codes(self) -> str:
        return json.dumps(
            {
                "CURRENT": "Released, before the LTS date, and not EOL.",
                "ACTIVE_LTS": "At or after the LTS date, before maintenance, and not EOL.",
                "MAINTENANCE_LTS": "At or after maintenance start, before EOL.",
                "END_OF_LIFE": "At or after the scheduled end date.",
                "NOT_YET_RELEASED": "Assessment date is before the scheduled start.",
                "SOURCE_CONFLICT": "Official and independent lifecycle registry disagree on a required field.",
                "UNRESOLVED": "A source, cycle, or required field could not be interpreted safely.",
            },
            sort_keys=True,
        )
