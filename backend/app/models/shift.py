"""Typed source records. No transport rules or inferred end dates."""

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Shift:
    employee_id: str = field(repr=False)
    last_name: str = field(repr=False)
    first_name: str = field(repr=False)
    department: str | None = field(repr=False)
    day: date
    task: str = field(repr=False)
    start_time: time
    end_time: time
    end_time_day_offset: int | None
    remark: str | None = field(repr=False)
    customer: str = field(repr=False)
    kms: Decimal | None
    source_file: str = field(repr=False)
    source_sheet: str
    source_row: int


@dataclass(frozen=True, slots=True)
class ImportIssue:
    """Contains metadata only: never the invalid source value."""

    code: str
    severity: str
    source_row: int | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class ImportReport:
    header_row: int
    data_rows_seen: int
    blank_rows: int
    summary_rows: int
    repeated_header_rows: int
    rejected_rows: int
    imported_rows: int
    outside_month_rows: int
    months: tuple[str, ...]
    selected_month: str | None
    source_sha256: str


@dataclass(frozen=True, slots=True)
class ImportResult:
    shifts: tuple[Shift, ...] = field(repr=False)
    issues: tuple[ImportIssue, ...]
    report: ImportReport

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "ERROR" for issue in self.issues)
