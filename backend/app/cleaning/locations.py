"""Manually confirmed dated location rules. Source kilometers are not evidence."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import tomllib



@dataclass(frozen=True, slots=True)
class LocationRule:
    customer: str
    location: str
    valid_from: date = date.min
    valid_until: date = date.max  # inclusive

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v.strip() for v in (self.customer, self.location)):
            raise ValueError("Location rule requires nonempty customer and location")
        if (type(self.valid_from) is not date or type(self.valid_until) is not date
                or self.valid_from > self.valid_until):
            raise ValueError("Invalid location rule dates")
        object.__setattr__(self, "customer", self.customer.strip().casefold())
        object.__setattr__(self, "location", self.location.strip())


def validate_rules(rules: tuple[LocationRule, ...]) -> None:
    for i, rule in enumerate(rules):
        if not isinstance(rule, LocationRule):
            raise ValueError("Invalid location rule")
        for other in rules[:i]:
            if (rule.customer == other.customer and
                    max(rule.valid_from, other.valid_from) <= min(rule.valid_until, other.valid_until)):
                raise ValueError("Overlapping confirmed customer location periods")


def load_location_rules(path: Path) -> tuple[str, tuple[LocationRule, ...]]:
    """No source values in errors, no writes. Unrecognized fields fail visibly."""
    try:
        with path.open('rb') as source:
            config = tomllib.load(source)
        if set(config) != {"version", "locations"}:
            raise ValueError
        version = config["version"]
        if not isinstance(version, str) or not version.strip() or not isinstance(config['locations'], list):
            raise ValueError
        rules = []
        for entry in config['locations']:
            if set(entry) - {"customer", "location", "valid_from", "valid_until"}:
                raise ValueError
            rules.append(LocationRule(**entry))
        rules = tuple(rules)
        validate_rules(rules)
        return version.strip(), rules
    except (OSError, ValueError, TypeError, KeyError) as from_error:
        raise ValueError("Invalid/unreadable location configuration") from from_error

