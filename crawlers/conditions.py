from abc import ABC, abstractmethod


class DoneCondition(ABC):
    @abstractmethod
    def check(self, records: list[dict]) -> tuple[bool, str]:
        """Return (passed, message)."""
        ...


class MinCount(DoneCondition):
    """Fail if fewer than n records."""

    def __init__(self, n: int):
        self.n = n

    def check(self, records):
        count = len(records)
        ok = count >= self.n
        return ok, f"MinCount({self.n}): got {count}"


class MaxCount(DoneCondition):
    """Fail if more than n records."""

    def __init__(self, n: int):
        self.n = n

    def check(self, records):
        count = len(records)
        ok = count <= self.n
        return ok, f"MaxCount({self.n}): got {count}"


class RequiredFields(DoneCondition):
    """Fail if any record is missing any of the listed fields."""

    def __init__(self, fields: list[str]):
        self.fields = fields

    def check(self, records):
        for r in records:
            for f in self.fields:
                if f not in r or r[f] is None:
                    return False, f"RequiredFields: record '{r.get('id', '?')}' missing '{f}'"
        return True, f"RequiredFields({self.fields}): all present"


class UniqueField(DoneCondition):
    """Fail if a field has duplicate values across records."""

    def __init__(self, field: str):
        self.field = field

    def check(self, records):
        seen = set()
        for r in records:
            val = r.get(self.field)
            if val in seen:
                return False, f"UniqueField({self.field}): duplicate '{val}'"
            seen.add(val)
        return True, f"UniqueField({self.field}): all unique ({len(records)} records)"


class FieldCoverage(DoneCondition):
    """Fail if fewer than threshold fraction of records have a non-None value."""

    def __init__(self, field: str, threshold: float = 0.9):
        self.field = field
        self.threshold = threshold

    def check(self, records):
        if not records:
            return False, f"FieldCoverage({self.field}): no records"
        filled = sum(1 for r in records if r.get(self.field) is not None)
        ratio = filled / len(records)
        ok = ratio >= self.threshold
        return ok, f"FieldCoverage({self.field}): {ratio:.1%} (threshold {self.threshold:.0%})"


class FieldCompleteness(DoneCondition):
    """Fail if any record has the field present but empty/whitespace-only."""

    def __init__(self, field: str):
        self.field = field

    def check(self, records):
        for r in records:
            val = r.get(self.field)
            if val is not None and isinstance(val, str) and not val.strip():
                return False, f"FieldCompleteness({self.field}): record '{r.get('id', '?')}' has blank value"
        return True, f"FieldCompleteness({self.field}): no blank values"
