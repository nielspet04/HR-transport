"""Clean only selected imported shifts; preserve evidence for later phases."""

from dataclasses import dataclass, field
from datetime import date

from app.models.shift import ImportResult, Shift
from .locations import LocationRule, validate_rules


def normalize_remark(value: str | None) -> str:
    # Whole-cell comparison only: no substring or inferred absence categories.
    return (value or "").strip().casefold()


@dataclass(frozen=True, slots=True)
class CleaningPolicy:
    """Explicit HR-confirmed extra exclusions, supplied by the caller."""

    excluded_remarks: tuple[str, ...] = field(default=(), repr=False)
    # Explicit user confirmation: these are ghost agents, not payable workers.
    ghost_employee_ids: tuple[str, ...] = field(
        default=("1112", "1113", "1114", "1115", "1116"), repr=False)
    # Confirmed physical co-location, NOT a transport-reference/tariff mapping.
    location_aliases: tuple[tuple[str, str], ...] = (
        ("DELTA AIRLINES", "LUCHTHAVEN"), ("HAINAN AIRLINES", "LUCHTHAVEN"),
        ("LATAM CARGO", "LUCHTHAVEN"), ("TUI", "LUCHTHAVEN"),
        ("ICTS BELGIUM BVBA", "LUCHTHAVEN"),
    )
    location_rules: tuple[LocationRule, ...] = ()
    location_config_version: str = "confirmed-airport-v2"

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip()
               for value in self.excluded_remarks):
            raise ValueError("Exclusion codes must be nonempty text")
        object.__setattr__(self, "excluded_remarks", tuple(sorted({
            normalize_remark(value) for value in self.excluded_remarks
        })))
        if any(not isinstance(value, str) or not value.strip()
               for value in self.ghost_employee_ids):
            raise ValueError("Ghost employee IDs must be nonempty text")
        object.__setattr__(self, "ghost_employee_ids", tuple(sorted({
            value.strip() for value in self.ghost_employee_ids
        })))
        aliases: dict[str, str] = {}
        for entry in self.location_aliases:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise ValueError("Location aliases must be customer/location pairs")
            customer, location = entry
            if any(not isinstance(value, str) or not value.strip()
                   for value in (customer, location)):
                raise ValueError("Location aliases must contain nonempty text")
            customer = customer.strip().casefold()
            location = location.strip()
            if customer in aliases and aliases[customer] != location:
                raise ValueError("Conflicting physical location aliases")
            aliases[customer] = location
        object.__setattr__(self, "location_aliases", tuple(sorted(aliases.items())))
        object.__setattr__(self, "location_rules", tuple(self.location_rules))
        validate_rules(self.location_rules)
        if any(rule.customer in aliases for rule in self.location_rules):
            raise ValueError("Customer has both undated alias and dated rule")
        if not isinstance(self.location_config_version, str) or not self.location_config_version.strip():
            raise ValueError("Location configuration version required")

    def location_for(self, customer: str, day: date) -> str | None:
        customer = customer.strip().casefold()
        for rule in self.location_rules:
            if rule.customer == customer and rule.valid_from <= day <= rule.valid_until:
                return rule.location
        return dict(self.location_aliases).get(customer)


@dataclass(frozen=True, slots=True)
class Movement:
    # No representative shift/tariff/time is chosen. All retained source evidence
    # survives grouping, including special remarks and differing km values.
    source_shifts: tuple[Shift, ...] = field(repr=False)
    physical_location: str = field(default="", repr=False)


@dataclass(frozen=True, slots=True)
class Removal:
    reason: str
    shift: Shift = field(repr=False)


@dataclass(frozen=True, slots=True)
class CleaningReport:
    selected_month: str | None
    input_rows: int
    telework_rows: int
    excluded_remark_rows: int
    duplicate_rows: int
    remaining_movements: int
    unresolved_remark_rows: int
    ghost_agent_rows: int = 0


@dataclass(frozen=True, slots=True)
class CleaningResult:
    movements: tuple[Movement, ...] = field(repr=False)
    removals: tuple[Removal, ...] = field(repr=False)
    unresolved_shifts: tuple[Shift, ...] = field(repr=False)
    policy: CleaningPolicy
    report: CleaningReport


def clean_import(imported: ImportResult, *,
                 policy: CleaningPolicy | None = None) -> CleaningResult:
    """Consume only importer-selected rows. Refuse incomplete/invalid imports."""
    if imported.has_errors:
        raise ValueError("Cleaning refused: resolve import errors first")
    month = imported.report.selected_month
    if month and any(shift.day.strftime("%Y-%m") != month
                     for shift in imported.shifts):
        raise ValueError("Cleaning refused: rows outside selected month")
    policy = policy if policy is not None else CleaningPolicy()
    excluded = set(policy.excluded_remarks)
    ghost_ids = set(policy.ghost_employee_ids)
    groups: dict[tuple[str, date, tuple[str, str]], list[Shift]] = {}
    removals: list[Removal] = []
    unresolved: list[Shift] = []
    telework_rows = excluded_rows = 0
    ghost_rows = 0
    for shift in imported.shifts:
        if shift.employee_id in ghost_ids:
            ghost_rows += 1
            removals.append(Removal("GHOST_AGENT", shift))
            continue
        remark = normalize_remark(shift.remark)
        if remark == "telework":
            telework_rows += 1
            removals.append(Removal("TELEWORK", shift))
            continue
        if remark in excluded:
            excluded_rows += 1
            removals.append(Removal("CONFIRMED_EXCLUDED_REMARK", shift))
            continue
        if remark:
            unresolved.append(shift)
        # Only explicit confirmed aliases share a physical location. Names not
        # in the mapping remain exact and in a separate namespace (no collision
        # with a source customer literally named LUCHTHAVEN).
        mapped = policy.location_for(shift.customer, shift.day)
        location_key = ("mapped", mapped) if mapped is not None else ("customer", shift.customer)
        key = (shift.employee_id, shift.day, location_key)
        if key in groups:
            removals.append(Removal("DUPLICATE_MOVEMENT", shift))
        groups.setdefault(key, []).append(shift)
    movements = tuple(Movement(tuple(shifts), key[2][1]) for key, shifts in groups.items())
    duplicates = sum(len(group.source_shifts) - 1 for group in movements)
    report = CleaningReport(month, len(imported.shifts), telework_rows,
                            excluded_rows, duplicates, len(movements), len(unresolved), ghost_rows)
    return CleaningResult(movements, tuple(removals), tuple(unresolved), policy, report)
