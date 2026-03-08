from __future__ import annotations
import re
import unicodedata
from functools import lru_cache
from typing import Any, TypedDict
from fastapi import HTTPException, status
from safetext import SafeText

MAX_MATCHES = 5
SUPPORTED_LANGUAGES: tuple[str, ...] = ("ru", "en")
MIN_BAD_WORD_LEN = 3
MAX_TOKEN_LEN_FOR_SCAN = 128
TOKEN_RE = re.compile(r"[\w@$!+|]+", re.UNICODE)
COMPACT_RE = re.compile(r"[\W_]+", re.UNICODE)

OBFUSCATION_CHAR_MAP = str.maketrans(
    {
        "a": "а",
        "b": "в",
        "c": "с",
        "e": "е",
        "h": "х",
        "i": "и",
        "j": "й",
        "k": "к",
        "m": "м",
        "o": "о",
        "p": "р",
        "t": "т",
        "u": "у",
        "v": "в",
        "x": "х",
        "y": "у",
        "0": "о",
        "1": "и",
        "3": "з",
        "4": "ч",
        "6": "б",
        "8": "в",
        "@": "а",
        "$": "с",
    }
)

OBFUSCATION_ALT_CHAR_MAP = str.maketrans(
    {
        "a": "а",
        "b": "в",
        "c": "с",
        "e": "е",
        "h": "х",
        "i": "и",
        "j": "й",
        "k": "к",
        "m": "м",
        "o": "о",
        "p": "р",
        "t": "т",
        "u": "у",
        "v": "в",
        "x": "х",
        "y": "й",
        "0": "о",
        "1": "и",
        "3": "з",
        "4": "ч",
        "6": "б",
        "8": "в",
        "@": "а",
        "$": "с",
    }
)

OBFUSCATION_STRICT_SEQ_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("shch", "щ"),
    ("sch", "щ"),
    ("yo", "е"),
    ("jo", "е"),
    ("yu", "ю"),
    ("ju", "ю"),
    ("ya", "я"),
    ("ja", "я"),
    ("zh", "ж"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ph", "ф"),
    ("th", "т"),
)

OBFUSCATION_STRICT_CHAR_MAP = str.maketrans(
    {
        "a": "а",
        "b": "в",
        "c": "с",
        "d": "д",
        "e": "е",
        "f": "ф",
        "g": "г",
        "h": "х",
        "i": "и",
        "j": "й",
        "k": "к",
        "l": "л",
        "m": "м",
        "n": "н",
        "o": "о",
        "p": "р",
        "q": "к",
        "r": "р",
        "s": "с",
        "t": "т",
        "u": "у",
        "v": "в",
        "w": "ш",
        "x": "х",
        "y": "й",
        "z": "з",
        "0": "о",
        "1": "и",
        "2": "з",
        "3": "з",
        "4": "ч",
        "5": "с",
        "6": "б",
        "7": "т",
        "8": "в",
        "9": "д",
        "@": "а",
        "$": "с",
        "!": "и",
        "+": "т",
        "|": "и",
        "α": "а",
        "β": "в",
        "γ": "г",
        "δ": "д",
        "ε": "е",
        "ζ": "з",
        "η": "н",
        "θ": "о",
        "ι": "и",
        "κ": "к",
        "λ": "л",
        "μ": "м",
        "ν": "н",
        "ο": "о",
        "ρ": "р",
        "σ": "с",
        "τ": "т",
        "υ": "у",
        "φ": "ф",
        "χ": "х",
        "ω": "о",
    }
)


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


def _normalize_basic(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).lower().replace("ё", "е")


def _normalize_obfuscated(value: str) -> str:
    normalized = _normalize_basic(value)
    return normalized.translate(OBFUSCATION_CHAR_MAP)


def _normalize_obfuscated_alt(value: str) -> str:
    normalized = _normalize_basic(value)
    return normalized.translate(OBFUSCATION_ALT_CHAR_MAP)


def _normalize_bad_word(raw_word: str) -> str:
    word = _normalize_basic(raw_word).strip()
    return _compact_for_scan(word)


def _compact_for_scan(value: str) -> str:
    return COMPACT_RE.sub("", value)


def _apply_strict_seq_replacements(value: str) -> str:
    out = value
    for src, dst in OBFUSCATION_STRICT_SEQ_REPLACEMENTS:
        out = out.replace(src, dst)
    return out


def _normalize_obfuscated_strict(value: str) -> str:
    normalized = _normalize_basic(value)
    normalized = _apply_strict_seq_replacements(normalized)
    return normalized.translate(OBFUSCATION_STRICT_CHAR_MAP)


@lru_cache(maxsize=1)
def _get_detectors() -> tuple[tuple[str, SafeText], ...]:
    return tuple((lang, SafeText(language=lang)) for lang in SUPPORTED_LANGUAGES)


@lru_cache(maxsize=1)
def _get_bad_words_index() -> dict[str, dict[int, set[str]]]:
    out: dict[str, dict[int, set[str]]] = {}

    for language, detector in _get_detectors():
        checker = getattr(detector, "checker", None)
        profanity_words = getattr(checker, "_profanity_words", None)
        if not isinstance(profanity_words, list):
            continue

        by_len: dict[int, set[str]] = {}
        for raw_word in profanity_words:
            if not isinstance(raw_word, str):
                continue

            word = _normalize_bad_word(raw_word)
            if not word or " " in word:
                continue
            if len(word) < MIN_BAD_WORD_LEN:
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


def _scan_token(token: str, *, token_start: int, language: str, by_len: dict[int, set[str]]) -> list[ModerationMatch]:
    if not token:
        return []

    variants: list[tuple[str, str, bool]] = []
    basic = _normalize_basic(token)
    if basic:
        variants.append(("basic", basic, True))

    obfuscated = _normalize_obfuscated(token)
    if obfuscated and obfuscated != basic:
        variants.append(("obfuscated", obfuscated, True))

    obfuscated_alt = _normalize_obfuscated_alt(token)
    if obfuscated_alt and obfuscated_alt not in {basic, obfuscated}:
        variants.append(("obfuscated_alt", obfuscated_alt, True))

    strict = _normalize_obfuscated_strict(token)
    if strict and strict not in {basic, obfuscated, obfuscated_alt}:
        variants.append(("obfuscated_strict", strict, True))

    compact = _compact_for_scan(obfuscated)
    if compact and compact != obfuscated:
        variants.append(("compact", compact, False))

    compact_alt = _compact_for_scan(obfuscated_alt)
    if compact_alt and compact_alt not in {obfuscated_alt, compact}:
        variants.append(("compact_alt", compact_alt, False))

    compact_strict = _compact_for_scan(strict)
    if compact_strict and compact_strict not in {strict, compact, compact_alt}:
        variants.append(("compact_strict", compact_strict, False))

    dedup: dict[str, tuple[str, bool]] = {}
    for variant_name, variant_text, has_direct_pos in variants:
        dedup.setdefault(variant_text, (variant_name, has_direct_pos))

    found: list[ModerationMatch] = []
    sorted_lengths = sorted(by_len.keys())
    for variant_text, (_, has_direct_pos) in dedup.items():
        variant_len = len(variant_text)
        if variant_len < MIN_BAD_WORD_LEN:
            continue

        for bad_len in sorted_lengths:
            if bad_len > variant_len:
                break

            words = by_len[bad_len]
            max_offset = variant_len - bad_len
            for offset in range(max_offset + 1):
                fragment = variant_text[offset: offset + bad_len]
                if fragment not in words:
                    continue

                if has_direct_pos:
                    start = token_start + offset
                    end = start + bad_len
                    word = token[offset: offset + bad_len]
                    found.append(
                        {
                            "word": word[:64],
                            "start": start,
                            "end": end,
                            "language": language,
                        }
                    )
                else:
                    found.append(
                        {
                            "word": token[:64],
                            "start": token_start,
                            "end": token_start + len(token),
                            "language": language,
                        }
                    )

    return found


def _scan_obfuscated_tokens(text: str) -> list[ModerationMatch]:
    indexes = _get_bad_words_index()
    if not indexes:
        return []

    found: list[ModerationMatch] = []
    for token_match in TOKEN_RE.finditer(text):
        token = token_match.group(0)
        if len(token) < MIN_BAD_WORD_LEN or len(token) > MAX_TOKEN_LEN_FOR_SCAN:
            continue

        token_start = token_match.start()
        for language, by_len in indexes.items():
            found.extend(
                _scan_token(
                    token,
                    token_start=token_start,
                    language=language,
                    by_len=by_len,
                )
            )

    return found


def detect_inappropriate_text(text: str) -> list[ModerationMatch]:
    value = str(text or "").strip()
    if not value:
        return []

    found: list[ModerationMatch] = []
    seen: set[tuple[str, int | None, int | None, str]] = set()

    variants: list[tuple[str, str]] = [("raw", value)]
    obfuscated_value = _normalize_obfuscated(value)
    if obfuscated_value != value:
        variants.append(("obfuscated", obfuscated_value))
    obfuscated_alt_value = _normalize_obfuscated_alt(value)
    if obfuscated_alt_value not in {value, obfuscated_value}:
        variants.append(("obfuscated_alt", obfuscated_alt_value))
    obfuscated_strict_value = _normalize_obfuscated_strict(value)
    if obfuscated_strict_value not in {value, obfuscated_value, obfuscated_alt_value}:
        variants.append(("obfuscated_strict", obfuscated_strict_value))

    compact_candidates = (
        obfuscated_value,
        obfuscated_alt_value,
        obfuscated_strict_value,
    )
    variant_values = {variant_value for _, variant_value in variants}
    for compact_source in compact_candidates:
        compact_value = _compact_for_scan(compact_source)
        if len(compact_value) < MIN_BAD_WORD_LEN:
            continue
        if compact_value in variant_values:
            continue
        variants.append(("compact", compact_value))
        variant_values.add(compact_value)

    for language, detector in _get_detectors():

        for variant_name, variant_value in variants:
            try:
                raw_matches = detector.check_profanity(text=variant_value) or []
            except Exception:
                continue

            if isinstance(raw_matches, dict):
                raw_matches = [raw_matches]
            if not isinstance(raw_matches, list):
                continue

            for raw in raw_matches:
                match = _normalize_match(raw, text=variant_value, language=language)
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

                if variant_name in {"obfuscated", "obfuscated_alt", "obfuscated_strict", "compact"}:
                    match = {
                        "word": str(match.get("word", ""))[:64],
                        "language": str(match.get("language", language))[:8],
                    }
                found.append(match)

    for match in _scan_obfuscated_tokens(value):
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


def _build_moderation_message(*, label: str, matches: list[ModerationMatch]) -> str:
    words: list[str] = []
    seen: set[str] = set()
    for match in matches:
        raw_word = match.get("word")
        if not isinstance(raw_word, str):
            continue

        word = raw_word.strip()
        if not word:
            continue

        key = _compact_for_scan(_normalize_obfuscated_strict(_normalize_obfuscated_alt(_normalize_obfuscated(word))))
        if key in seen:
            continue

        seen.add(key)
        words.append(word)

    if not words:
        return f"{label} содержит неподобающие слова."

    return f"{label} содержит неподобающие слова: {', '.join(words)}."


def enforce_clean_text(*, field: str, label: str, value: str) -> None:
    matches = detect_inappropriate_text(value)
    if not matches:
        return

    detail: ModerationDetail = {
        "code": "inappropriate_text_detected",
        "field": field,
        "message": _build_moderation_message(label=label, matches=matches),
        "matches": matches,
    }
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
