"""Canonical policy catalog shared by API reads and draft provenance validation."""

import hashlib
import re

from app.storage import ROOT


def policies():
    sections = {}
    for path in sorted((ROOT / "knowledge_base").glob("*.md")):
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        for match in re.finditer(r"^## ([^\n]+)\r?\n(.*?)(?=^## |\Z)", text, re.M | re.S):
            heading, body = match.groups()
            heading = heading.strip()
            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            section_id = path.name + "#" + slug
            sections[section_id] = dict(
                section_id=section_id,
                filename=path.name,
                heading=heading,
                body=body.strip(),
                source_hash=hashlib.sha256(raw).hexdigest(),
            )
    return sections
