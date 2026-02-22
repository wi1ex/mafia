from __future__ import annotations
import re
import unicodedata
from functools import lru_cache
from typing import Any, TypedDict
from fastapi import HTTPException, status
from safetext import SafeText

MAX_MATCHES = 5
SUPPORTED_LANGUAGES: tuple[str, ...] = ("ru", "en")

AGGRESSIVE_JOIN_LANGUAGES: tuple[str, ...] = ("ru",)
MIN_EDGE_WORD_LEN = 3
TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]+")


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


def _normalize_for_join_scan(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).lower().replace("ё", "е")


@lru_cache(maxsize=1)
def _get_detectors() -> tuple[tuple[str, SafeText], ...]:
    return tuple((lang, SafeText(language=lang)) for lang in SUPPORTED_LANGUAGES)


@lru_cache(maxsize=1)
def _get_join_edge_indexes() -> dict[str, dict[int, set[str]]]:
    out: dict[str, dict[int, set[str]]] = {}
    for language, detector in _get_detectors():
        if language not in AGGRESSIVE_JOIN_LANGUAGES:
            continue

        checker = getattr(detector, "checker", None)
        profanity_words = getattr(checker, "_profanity_words", None)
        if not isinstance(profanity_words, list):
            continue

        by_len: dict[int, set[str]] = {}
        for raw_word in profanity_words:
            if not isinstance(raw_word, str):
                continue
            word = _normalize_for_join_scan(raw_word.strip())
            if not word or " " in word:
                continue
            if len(word) < MIN_EDGE_WORD_LEN:
                continue
            by_len.setdefault(len(word), set()).add(word)

        if by_len:
            out[language] = by_len

    return out


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


def _scan_joined_tokens(text: str) -> list[ModerationMatch]:
    indexes = _get_join_edge_indexes()
    if not indexes:
        return []

    found: list[ModerationMatch] = []
    for tok in TOKEN_RE.finditer(text):
        token = tok.group(0)
        norm_token = _normalize_for_join_scan(token)
        token_len = len(norm_token)
        if token_len < MIN_EDGE_WORD_LEN + 1:
            continue

        token_start = tok.start()
        for language, by_len in indexes.items():
            for bad_len, words_set in by_len.items():
                if token_len <= bad_len:
                    continue

                prefix = norm_token[:bad_len]
                if prefix in words_set:
                    start = token_start
                    end = token_start + bad_len
                    found.append(
                        {
                            "word": text[start:end][:64],
                            "start": start,
                            "end": end,
                            "language": language,
                        }
                    )

                suffix = norm_token[token_len - bad_len :]
                if suffix in words_set:
                    start = token_start + (token_len - bad_len)
                    end = token_start + token_len
                    found.append(
                        {
                            "word": text[start:end][:64],
                            "start": start,
                            "end": end,
                            "language": language,
                        }
                    )

    return found


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

    for match in _scan_joined_tokens(value):
        key = (
            match.get("word", "").lower(),
            match.get("start"),
            match.get("end"),
            match.get("language", ""),
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
