"""Rule-based, auditable feature extraction for job descriptions."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Union

Number = Union[int, float]


@dataclass(frozen=True)
class ExperienceRange:
    """Minimum and maximum years found in a description.

    ``maximum=None`` means the requirement is open-ended. Both values are
    ``None`` when no requirement can be inferred.
    """

    minimum: Number | None
    maximum: Number | None


DEFAULT_SKILLS: Mapping[str, Sequence[str]] = {
    "Python": ("python", "python3"),
    "SQL": ("sql", "mysql", "postgresql", "postgres", "t-sql"),
    "pandas": ("pandas",),
    "NumPy": ("numpy",),
    "Machine Learning": ("machine learning", "机器学习", "ml"),
    "Deep Learning": ("deep learning", "深度学习", "dl"),
    "PyTorch": ("pytorch", "torch"),
    "TensorFlow": ("tensorflow",),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "Java": ("java",),
    "JavaScript": ("javascript", "typescript", "node.js", "nodejs"),
    "Excel": ("excel", "microsoft excel", "电子表格"),
    "R": ("r", "r language", "r语言"),
    "C++": ("c++", "cpp"),
    "Spark": ("spark", "pyspark"),
    "Tableau": ("tableau",),
    "Power BI": ("power bi", "powerbi"),
}

_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CHINESE_NUMBER = re.compile(r"[零〇一二两三四五六七八九十]+(?=\s*(?:年|[-~～—–至到]))")
_NUMBER = r"\d+(?:\.\d+)?"
_YEAR_UNIT = r"(?:years?|yrs?\.?|年)"

_RANGE_PATTERNS = (
    re.compile(
        rf"(?P<minimum>{_NUMBER})\s*(?:-|~|～|—|–|to|through|至|到)\s*"
        rf"(?P<maximum>{_NUMBER})\s*{_YEAR_UNIT}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"between\s+(?P<minimum>{_NUMBER})\s+and\s+"
        rf"(?P<maximum>{_NUMBER})\s*{_YEAR_UNIT}",
        re.IGNORECASE,
    ),
)
_UPPER_BOUND_PATTERNS = (
    re.compile(
        rf"(?:up\s+to|at\s+most|maximum(?:\s+of)?|under|不超过|最多)\s*"
        rf"(?P<maximum>{_NUMBER})\s*{_YEAR_UNIT}",
        re.IGNORECASE,
    ),
    re.compile(rf"(?P<maximum>{_NUMBER})\s*年\s*(?:以下|以内)"),
)
_LOWER_BOUND_PATTERNS = (
    re.compile(
        rf"(?:at\s+least|minimum(?:\s+of)?|min\.?|more\s+than|over|至少|最低)\s*"
        rf"(?P<minimum>{_NUMBER})\s*{_YEAR_UNIT}",
        re.IGNORECASE,
    ),
    re.compile(rf"(?P<minimum>{_NUMBER})\s*(?:\+\s*{_YEAR_UNIT}?|年\s*(?:以上|起))", re.I),
)
_SINGLE_YEAR = re.compile(rf"(?P<minimum>{_NUMBER})\s*{_YEAR_UNIT}", re.IGNORECASE)

_NO_EXPERIENCE_PHRASES = (
    "no experience required",
    "experience not required",
    "no prior experience",
    "无需经验",
    "无经验要求",
    "经验不限",
)
_FRESH_GRADUATE_PHRASES = (
    "fresh graduate",
    "recent graduate",
    "new graduate",
    "应届",
    "应届生",
    "应届毕业生",
)


def _chinese_to_int(token: str) -> int:
    if "十" in token:
        before, after = token.split("十", 1)
        tens = _CHINESE_DIGITS.get(before, 1) if before else 1
        ones = _CHINESE_DIGITS.get(after, 0) if after else 0
        return tens * 10 + ones
    digits = "".join(str(_CHINESE_DIGITS[char]) for char in token)
    return int(digits)


def _normalise_for_matching(value: object) -> str:
    text = "" if value is None else unicodedata.normalize("NFKC", str(value)).casefold()
    return _CHINESE_NUMBER.sub(lambda match: str(_chinese_to_int(match.group(0))), text)


def _number(value: str) -> Number:
    parsed = float(value)
    return int(parsed) if parsed.is_integer() else parsed


def extract_experience_range(text: object) -> ExperienceRange:
    """Extract English or Chinese experience requirements.

    Examples include ``1-3 years``, ``at least 2 years``, ``三至五年``,
    ``3年以上``, and fresh-graduate wording.
    """

    normalised = _normalise_for_matching(text)

    for pattern in _RANGE_PATTERNS:
        match = pattern.search(normalised)
        if match:
            minimum = _number(match.group("minimum"))
            maximum = _number(match.group("maximum"))
            if minimum > maximum:
                minimum, maximum = maximum, minimum
            return ExperienceRange(minimum, maximum)

    for phrase in _FRESH_GRADUATE_PHRASES:
        if phrase in normalised:
            return ExperienceRange(0, 0)
    for phrase in _NO_EXPERIENCE_PHRASES:
        if phrase in normalised:
            return ExperienceRange(0, None)

    for pattern in _UPPER_BOUND_PATTERNS:
        match = pattern.search(normalised)
        if match:
            return ExperienceRange(0, _number(match.group("maximum")))

    for pattern in _LOWER_BOUND_PATTERNS:
        match = pattern.search(normalised)
        if match:
            return ExperienceRange(_number(match.group("minimum")), None)

    match = _SINGLE_YEAR.search(normalised)
    if match:
        return ExperienceRange(_number(match.group("minimum")), None)
    return ExperienceRange(None, None)


def extract_experience(text: object) -> Number | None:
    """Backward-compatible helper returning the minimum required years."""

    return extract_experience_range(text).minimum


def classify_experience(minimum: Number | None, maximum: Number | None = None) -> str:
    """Map a requirement to a stable, documented seniority bucket."""

    del maximum  # Reserved for future bucket policies.
    if minimum is None:
        return "unknown"
    if minimum <= 0:
        return "entry"
    if minimum < 3:
        return "junior"
    if minimum < 6:
        return "mid"
    return "senior"


def _compile_alias(alias: str) -> re.Pattern[str]:
    normalised = _normalise_for_matching(alias).strip()
    if not normalised:
        raise ValueError("skill aliases must not be empty")
    expression = re.escape(normalised).replace(r"\ ", r"\s+")
    if re.match(r"[a-z0-9_]", normalised[0], flags=re.IGNORECASE):
        expression = r"(?<![a-z0-9_])" + expression
    if re.match(r"[a-z0-9_]", normalised[-1], flags=re.IGNORECASE):
        expression += r"(?![a-z0-9_])"
    return re.compile(expression, re.IGNORECASE)


class SkillExtractor:
    """Boundary-safe matcher built from canonical skills and their aliases."""

    def __init__(self, skills: Mapping[str, Sequence[str]]):
        if not isinstance(skills, Mapping) or not skills:
            raise ValueError("skills must be a non-empty mapping")

        compiled: list[tuple[str, tuple[re.Pattern[str], ...]]] = []
        for canonical, aliases in skills.items():
            canonical_name = str(canonical).strip()
            if not canonical_name:
                raise ValueError("canonical skill names must not be empty")
            if isinstance(aliases, str) or not isinstance(aliases, Sequence):
                raise ValueError(f"aliases for {canonical_name!r} must be a list")
            unique_aliases = dict.fromkeys([canonical_name, *[str(alias) for alias in aliases]])
            patterns = tuple(_compile_alias(alias) for alias in unique_aliases)
            compiled.append((canonical_name, patterns))
        self._compiled = tuple(compiled)

    def extract(self, text: object) -> list[str]:
        normalised = _normalise_for_matching(text)
        return [
            canonical
            for canonical, patterns in self._compiled
            if any(pattern.search(normalised) for pattern in patterns)
        ]


def load_skill_config(path: str | Path) -> Mapping[str, Sequence[str]]:
    """Load a UTF-8 JSON mapping of canonical skill names to alias arrays."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("skill config must be a JSON object")
    # Construction validates the full payload now, close to the user's input.
    SkillExtractor(payload)
    return payload


_DEFAULT_EXTRACTOR = SkillExtractor(DEFAULT_SKILLS)


def extract_skills(text: object, skills: Mapping[str, Sequence[str]] | None = None) -> list[str]:
    """Extract canonical skills with token boundaries to prevent substrings."""

    extractor = _DEFAULT_EXTRACTOR if skills is None else SkillExtractor(skills)
    return extractor.extract(text)


def extract_features(text: object, extractor: SkillExtractor | None = None) -> dict[str, object]:
    """Extract experience and skills from one description."""

    experience = extract_experience_range(text)
    skill_extractor = extractor or _DEFAULT_EXTRACTOR
    return {
        "experience_min_years": experience.minimum,
        "experience_max_years": experience.maximum,
        "experience_level": classify_experience(experience.minimum, experience.maximum),
        "skills": skill_extractor.extract(text),
    }
