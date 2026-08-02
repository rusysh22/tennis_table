import re
import unicodedata
import uuid


IMPORT_NAMESPACE = uuid.UUID("de19a263-e3df-4e0a-b6a2-00a3ad143b56")


def slugify(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "item"


def stable_uuid(*parts):
    key = "/".join(str(part).strip() for part in parts)
    return str(uuid.uuid5(IMPORT_NAMESPACE, key))
