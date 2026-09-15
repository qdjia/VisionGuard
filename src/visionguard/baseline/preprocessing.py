"""Conservative cleaning; no Chinese stemming or English stopword removal."""

import re
import unicodedata


def clean_text(text: str, *, lowercase: bool = False) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    text = re.sub(r"\s+", " ", text).strip()
    text = "".join(c for c in text if unicodedata.category(c) != "Cc")
    if not text:
        raise ValueError("text is empty after preprocessing")
    return text.lower() if lowercase else text
