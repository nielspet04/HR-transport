"""Only requested bootstrap data, plus provenance and validation metadata."""
from dataclasses import dataclass, field
from decimal import Decimal
from .shift import ImportIssue


@dataclass(frozen=True, slots=True)
class ReferenceRecord:
    employee_name: str | None = field(repr=False)
    location: str | None = field(repr=False)
    distance: Decimal | None
    transport_mode: str | None
    unresolved: tuple[str, ...]
    source_values: tuple[tuple[str, object], ...] = field(repr=False)
    source_row: int


@dataclass(frozen=True, slots=True)
class ReferenceReport:
    header_row: int
    data_rows_seen: int
    blank_rows: int
    repeated_header_rows: int
    ignored_nondata_rows: int
    ignored_special_rows: int
    imported_rows: int
    unresolved_rows: int
    source_sha256: str


@dataclass(frozen=True, slots=True)
class ReferenceResult:
    records: tuple[ReferenceRecord, ...] = field(repr=False)
    issues: tuple[ImportIssue, ...]
    report: ReferenceReport

    @property
    def has_errors(self) -> bool:
        return any(i.severity == 'ERROR' for i in self.issues)
