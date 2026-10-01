import ipaddress
import re
from urllib.parse import urlparse

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
UPI_RE = re.compile(r"^[a-z0-9.\-_]{2,}@[a-z]{2,}$")


def mask_aadhaar(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return f"XXXX-XXXX-{digits[-4:]}" if len(digits) == 12 else value


def normalize_phone(value: str, default_country_code: str = "+91") -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return f"{default_country_code}{digits[1:]}"
    if len(digits) == 10 and digits[0] in "6789":
        return f"{default_country_code}{digits}"
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return f"+{digits}"
    if len(digits) == 13 and digits.startswith("091") and digits[3] in "6789":
        return f"+{digits[1:]}"
    return value.strip()


def normalize_upi(value: str) -> str:
    candidate = value.strip().lower()
    return candidate if UPI_RE.match(candidate) else value.strip()


def normalize_ifsc(value: str) -> str:
    candidate = value.strip().upper()
    return candidate if IFSC_RE.match(candidate) else value.strip()


def normalize_pan(value: str) -> str:
    candidate = value.strip().upper()
    return candidate if PAN_RE.match(candidate) else value.strip()


def canonicalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{value.strip()}")
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{host}{path}"


def extract_domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").lower()


def validate_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return value.strip()
