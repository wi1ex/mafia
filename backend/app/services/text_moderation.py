from __future__ import annotations
from functools import lru_cache
from typing import Any, TypedDict
from fastapi import HTTPException, status
from safetext import SafeText

MAX_MATCHES = 5
SUPPORTED_LANGUAGES: tuple[str, ...] = ("ru", "en")


class ModerationMatch(TypedDict, total=False):
    word: str
    start: int
    end: int
    language: str


class ModerationDetail(TypedDict):
    code: str
    field: str
    message: str
    matches: list[ModerationMatch]


def _to_int(raw: Any) -> int | None:
    try:
        return int(raw)
    except Exception:
        return None


@lru_cache(maxsize=1)
def _get_detectors() -> tuple[tuple[str, SafeText], ...]:
    return tuple((lang, SafeText(language=lang)) for lang in SUPPORTED_LANGUAGES)


def _normalize_match(raw: Any, *, text: str, language: str) -> ModerationMatch | None:
    if not isinstance(raw, dict):
        return None

    start = _to_int(raw.get("start"))
    end = _to_int(raw.get("end"))

    raw_word = raw.get("word")
    word = raw_word.strip() if isinstance(raw_word, str) else ""
    if not word and start is not None and end is not None and 0 <= start < end <= len(text):
        word = text[start:end]
    if not word:
        return None

    match: ModerationMatch = {"word": word[:64], "language": language}
    if start is not None:
        match["start"] = start
    if end is not None:
        match["end"] = end
    return match


def detect_inappropriate_text(text: str) -> list[ModerationMatch]:
    value = str(text or "").strip()
    if not value:
        return []

    found: list[ModerationMatch] = []
    seen: set[tuple[str, int | None, int | None, str]] = set()
    for language, detector in _get_detectors():
        try:
            raw_matches = detector.check_profanity(text=value) or []
        except Exception:
            continue

        if isinstance(raw_matches, dict):
            raw_matches = [raw_matches]
        if not isinstance(raw_matches, list):
            continue

        for raw in raw_matches:
            match = _normalize_match(raw, text=value, language=language)
            if not match:
                continue
            key = (
                match.get("word", "").lower(),
                match.get("start"),
                match.get("end"),
                match.get("language", language),
            )
            if key in seen:
                continue
            seen.add(key)
            found.append(match)

    found.sort(key=lambda item: (item.get("start", 10**9), item.get("word", "")))
    return found[:MAX_MATCHES]


def enforce_clean_text(*, field: str, label: str, value: str) -> None:
    matches = detect_inappropriate_text(value)
    if not matches:
        return

    words = [str(m.get("word")) for m in matches if m.get("word")]
    words_unique = list(dict.fromkeys(words))
    words_str = ", ".join(words_unique)
    extra = f" Найдено: {words_str}." if words_str else ""
    detail: ModerationDetail = {
        "code": "inappropriate_text_detected",
        "field": field,
        "message": f"{label} содержит неподобающие слова.{extra}",
        "matches": matches,
    }
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
