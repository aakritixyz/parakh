import re

from app.normalize import (
    canonicalize_email,
    mask_aadhaar,
    normalize_ifsc,
    normalize_pan,
    normalize_phone,
    normalize_upi,
    normalize_url,
    validate_ip,
)

AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[-\s]?|0)?[6-9]\d{4}[-\s]?\d{5}(?!\d)")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
URL_RE = re.compile(r"https?://[^\s)]+")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
UPI_RE = re.compile(r"\b[\w.\-]{2,}@[a-zA-Z]{2,}\b")
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)


def extract_entities(text: str) -> list[dict]:
    patterns = [
        ("aadhaar", AADHAAR_RE),
        ("pan", PAN_RE),
        ("phone", PHONE_RE),
        ("email", EMAIL_RE),
        ("url", URL_RE),
        ("ip", IP_RE),
        ("upi", UPI_RE),
        ("ifsc", IFSC_RE),
    ]
    entities = []
    for kind, regex in patterns:
        for match in regex.finditer(text):
            value = match.group(0)
            canonical = normalize_entity(kind, value)
            entities.append({"kind": kind, "value": value, "canonical": canonical, "masked": kind == "aadhaar"})
    return entities


def normalize_entity(kind: str, value: str) -> str:
    if kind == "aadhaar":
        return mask_aadhaar(value)
    if kind == "phone":
        return normalize_phone(value)
    if kind == "upi":
        return normalize_upi(value)
    if kind == "ifsc":
        return normalize_ifsc(value)
    if kind == "pan":
        return normalize_pan(value)
    if kind == "email":
        return canonicalize_email(value)
    if kind == "url":
        return normalize_url(value)
    if kind == "ip":
        return validate_ip(value)
    return value.strip().lower()
