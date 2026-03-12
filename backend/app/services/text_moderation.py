from __future__ import annotations
import re
import unicodedata
from functools import lru_cache
from typing import Any, TypedDict
from fastapi import HTTPException, status
from safetext import SafeText

MAX_MATCHES = 5
MIN_BAD_WORD_LEN = 3
MAX_TOKEN_LEN_FOR_SCAN = 128
SUPPORTED_LANGUAGES: tuple[str, ...] = ("ru", "en")
TOKEN_SCAN_LANGUAGES: tuple[str, ...] = ("ru",)
TOKEN_RE = re.compile(r"[\w@$!+|]+", re.UNICODE)
COMPACT_RE = re.compile(r"[\W_]+", re.UNICODE)
REPEATED_CHAR_RE = re.compile(r"(.)\1+")

BRIDGE_DROP_CHARS = frozenset({"i", "j", "l", "1", "!", "|", "и", "й", "і", "ӏ", "ı"})

COMMON_OBFUSCATION_MAP = {
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
    "ı": "и",
    "і": "и",
    "ӏ": "и",
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
    "π": "п",
    "ρ": "р",
    "σ": "с",
    "τ": "т",
    "υ": "у",
    "φ": "ф",
    "χ": "х",
    "ω": "о",
    "∏": "п",
}

COMMON_OBFUSCATION_ALT_OVERRIDES = {"y": "й"}

STRICT_OBFUSCATION_OVERRIDES = {
    "d": "д",
    "f": "ф",
    "g": "г",
    "l": "л",
    "n": "н",
    "q": "к",
    "r": "р",
    "s": "с",
    "w": "ш",
    "z": "з",
    "2": "з",
    "5": "с",
    "7": "т",
    "9": "д",
    "!": "и",
    "+": "т",
    "|": "и",
}

STRICT_OBFUSCATION_ALT_OVERRIDES = {"n": "п", "y": "й"}

OBFUSCATION_CHAR_MAP = str.maketrans(COMMON_OBFUSCATION_MAP)
OBFUSCATION_ALT_CHAR_MAP = str.maketrans(COMMON_OBFUSCATION_MAP | COMMON_OBFUSCATION_ALT_OVERRIDES)
OBFUSCATION_STRICT_CHAR_MAP = str.maketrans(COMMON_OBFUSCATION_MAP | STRICT_OBFUSCATION_OVERRIDES)
OBFUSCATION_STRICT_ALT_CHAR_MAP = str.maketrans(COMMON_OBFUSCATION_MAP | STRICT_OBFUSCATION_OVERRIDES | STRICT_OBFUSCATION_ALT_OVERRIDES)

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


def _strip_invisible_and_marks(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", str(value or "")))
    out: list[str] = []
    for char in normalized:
        category = unicodedata.category(char)
        if category.startswith("M") or category in {"Cc", "Cf", "Cn", "Co", "Cs"}:
            continue
        out.append(char)
    return unicodedata.normalize("NFKC", "".join(out))


def _normalize_basic(value: str) -> str:
    return _strip_invisible_and_marks(value).lower().replace("ё", "е")


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


def _normalize_obfuscated_strict(value: str, *, alt: bool = False) -> str:
    normalized = _normalize_basic(value)
    normalized = _apply_strict_seq_replacements(normalized)
    table = OBFUSCATION_STRICT_ALT_CHAR_MAP if alt else OBFUSCATION_STRICT_CHAR_MAP
    return normalized.translate(table)


def _char_script(char: str) -> str:
    code = ord(char)
    if (
        0x0400 <= code <= 0x052F
        or 0x1C80 <= code <= 0x1C8F
        or 0x2DE0 <= code <= 0x2DFF
        or 0xA640 <= code <= 0xA69F
    ):
        return "cyrl"

    if 0x0041 <= code <= 0x024F:
        return "latn"

    if 0x0370 <= code <= 0x03FF or 0x1F00 <= code <= 0x1FFF:
        return "grek"

    if char.isdigit():
        return "digit"

    return "other"


def _drop_foreign_script_noise(value: str) -> str:
    counts = {"cyrl": 0, "latn": 0, "grek": 0}
    for char in value:
        if not char.isalpha():
            continue
        script = _char_script(char)
        if script in counts:
            counts[script] += 1
    primary_script = max(counts, key=counts.get)
    non_zero_scripts = sum(1 for count in counts.values() if count > 0)
    if counts[primary_script] == 0 or non_zero_scripts < 2:
        return value

    out: list[str] = []
    for char in value:
        script = _char_script(char)
        if char.isalpha() and script in counts and script != primary_script:
            continue
        out.append(char)
    return "".join(out)


def _drop_bridge_chars(value: str) -> str:
    if len(value) < 3:
        return value

    out = [value[0]]
    for char in value[1:-1]:
        if char in BRIDGE_DROP_CHARS:
            continue
        out.append(char)
    out.append(value[-1])
    return "".join(out)


def _squeeze_repeats(value: str) -> str:
    return REPEATED_CHAR_RE.sub(r"\1", value)


def _add_variant(variants: list[tuple[str, str, bool]], seen: set[str], *, name: str, text: str, has_direct_pos: bool) -> None:
    if not text or len(text) < MIN_BAD_WORD_LEN:
        return

    if text in seen:
        return

    seen.add(text)
    variants.append((name, text, has_direct_pos))


def _build_variants(value: str) -> list[tuple[str, str, bool]]:
    basic = _normalize_basic(value)
    variants: list[tuple[str, str, bool]] = []
    seen: set[str] = set()
    direct_variants = (
        ("basic", basic, True),
        ("obfuscated", _normalize_obfuscated(value), True),
        ("obfuscated_alt", _normalize_obfuscated_alt(value), True),
        ("obfuscated_strict", _normalize_obfuscated_strict(value), False),
        ("obfuscated_strict_alt", _normalize_obfuscated_strict(value, alt=True), False),
        ("foreign_strip", _drop_foreign_script_noise(basic), False),
    )

    for name, text, has_direct_pos in direct_variants:
        _add_variant(variants, seen, name=name, text=text, has_direct_pos=has_direct_pos)
        compact = _compact_for_scan(text)
        _add_variant(variants, seen, name=f"{name}_compact", text=compact, has_direct_pos=False)
        bridge = _drop_bridge_chars(compact)
        _add_variant(variants, seen, name=f"{name}_bridge", text=bridge, has_direct_pos=False)
        squeezed = _squeeze_repeats(bridge)
        _add_variant(variants, seen, name=f"{name}_squeezed", text=squeezed, has_direct_pos=False)

    return variants


@lru_cache(maxsize=1)
def _get_detectors() -> tuple[tuple[str, SafeText], ...]:
    return tuple((lang, SafeText(language=lang)) for lang in SUPPORTED_LANGUAGES)


@lru_cache(maxsize=1)
def _get_bad_words_index() -> dict[str, dict[int, set[str]]]:
    out: dict[str, dict[int, set[str]]] = {}
    for language, detector in _get_detectors():
        if language not in TOKEN_SCAN_LANGUAGES:
            continue
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

    found: list[ModerationMatch] = []
    sorted_lengths = sorted(by_len.keys())
    for _, variant_text, has_direct_pos in _build_variants(token):
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
                if has_direct_pos and variant_len == len(token):
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
    for language, detector in _get_detectors():
        for _, variant_value, has_direct_pos in _build_variants(value):
            try:
                raw_matches = detector.check_profanity(text=variant_value) or []
            except Exception:
                continue
            if isinstance(raw_matches, dict):
                raw_matches = [raw_matches]
            if not isinstance(raw_matches, list):
                continue

            source_text = value if has_direct_pos and len(variant_value) == len(value) else variant_value
            for raw in raw_matches:
                match = _normalize_match(raw, text=source_text, language=language)
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
                if source_text is not value:
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


def _dedupe_match_word(word: str) -> str:
    normalized = _normalize_obfuscated_strict(word, alt=True)
    normalized = _compact_for_scan(normalized)
    normalized = _drop_bridge_chars(normalized)
    return _squeeze_repeats(normalized)


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

        key = _dedupe_match_word(word)
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
