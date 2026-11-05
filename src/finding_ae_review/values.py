"""Field-specific representation rules; zero, No, and null remain distinct."""
from datetime import datetime
from decimal import Decimal, InvalidOperation


def null(value, config):
    return value is None or str(value) in config.get("null_tokens", [""])


def normalize(value, metadata, config):
    if null(value, config):
        return None
    raw = str(value)
    mapped = metadata.get("value_map", {}).get(raw, raw)
    if null(mapped, config):
        return None
    kind = metadata.get("type", "text")
    if kind in {"date", "time"}:
        for fmt in metadata.get("formats", []):
            try:
                parsed = datetime.strptime(mapped.strip(), fmt)
                return parsed.date().isoformat() if kind == "date" else parsed.time().isoformat()
            except ValueError:
                pass
        raise ValueError(f"Invalid {kind} representation")
    if kind == "number":
        try:
            value = Decimal(mapped.strip())
            if not value.is_finite():
                raise ValueError("Non-finite number")
            return value.normalize()
        except InvalidOperation as exc:
            raise ValueError("Invalid numeric representation") from exc
    return mapped if metadata.get("case_sensitive", True) else mapped.casefold()


def equal(left, right, metadata, config):
    try:
        return normalize(left, metadata, config) == normalize(right, metadata, config)
    except ValueError:
        return False

