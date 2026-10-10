from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


SanctionBadgeKey = Literal[
    "ban", "tm1", "tm2", "tm3", "tm4", "ot1", "ot2", "ot3", "ot4",
    "foul", "tech_foul", "removal", "ppk",
]


class SanctionRuleItem(BaseModel):
    text: str = Field(min_length=1, max_length=1024)
    badges: list[SanctionBadgeKey] = Field(default_factory=list, max_length=2)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_badge(cls, value: Any) -> Any:
        if isinstance(value, Mapping) and "badges" not in value:
            badge = value.get("badge")
            return {**value, "badges": [badge] if badge is not None else []}

        return value

    @field_validator("badges")
    @classmethod
    def validate_unique_badges(cls, value: list[SanctionBadgeKey]) -> list[SanctionBadgeKey]:
        if len(value) != len(set(value)):
            raise ValueError("rule_badges_must_be_unique")

        return value

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("rule_text_required")

        return normalized


class SanctionRulesSection(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=255)
    rules: list[SanctionRuleItem] = Field(min_length=1, max_length=100)

    @field_validator("id", "title")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("rule_section_value_required")

        return normalized


class SanctionRulesOut(BaseModel):
    sections: list[SanctionRulesSection] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_unique_section_ids(self):
        ids = [section.id for section in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("rule_section_ids_must_be_unique")

        return self


class SanctionRulesUpdateIn(SanctionRulesOut):
    @field_validator("sections", mode="before")
    @classmethod
    def require_explicit_badges(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            for section in value:
                rules = section.get("rules") if isinstance(section, Mapping) else None
                if isinstance(rules, (list, tuple)) and any(
                    isinstance(rule, Mapping) and "badges" not in rule for rule in rules
                ):
                    raise ValueError("rule_badges_required")

        return value
