from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemorySource(StrEnum):
    USER_EXPLICIT = "USER_EXPLICIT"
    USER_CORRECTION = "USER_CORRECTION"
    USER_PROFILE = "USER_PROFILE"
    CONVERSATION_INFERENCE = "CONVERSATION_INFERENCE"
    SYSTEM = "SYSTEM"
    IMPORTED = "IMPORTED"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PrivacyLevel(StrEnum):
    NORMAL = "NORMAL"
    PRIVATE = "PRIVATE"
    HIGHLY_PRIVATE = "HIGHLY_PRIVATE"


class Retention(StrEnum):
    TEMPORARY = "TEMPORARY"
    DURABLE = "DURABLE"
    LONG_TERM = "LONG_TERM"


class MemoryKind(StrEnum):
    IDENTITY = "IDENTITY"
    RELATIONSHIP = "RELATIONSHIP"
    PREFERENCE = "PREFERENCE"
    FACT = "FACT"
    GOAL = "GOAL"
    PROJECT = "PROJECT"
    EVENT = "EVENT"
    DECISION = "DECISION"
    HABIT = "HABIT"
    INTEREST = "INTEREST"
    ASTROLOGY = "ASTROLOGY"
    TEMPORAL = "TEMPORAL"
    CONTEXTUAL = "CONTEXTUAL"


class UserProfile(BaseModel):
    preferred_name: str | None = None
    date_of_birth: str | None = None
    birth_time: str | None = None
    birth_place: str | None = None
    location: str | None = None
    timezone: str | None = None
    languages: list[str] = Field(default_factory=list)
    education: dict[str, Any] = Field(default_factory=dict)
    work: dict[str, Any] = Field(default_factory=dict)
    career: dict[str, Any] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    communication_style: dict[str, Any] = Field(default_factory=dict)
    personality_notes: list[str] = Field(default_factory=list)
    important_dates: dict[str, Any] = Field(default_factory=dict)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    goals: list[dict[str, Any]] = Field(default_factory=list)
    habits: list[str] = Field(default_factory=list)
    long_term_context: list[str] = Field(default_factory=list)
    astrology_profile: dict[str, Any] = Field(default_factory=dict)


class RelationshipCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    relationship_type: str = Field(default="other", max_length=50)
    important_dates: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=5000)
    confidence: Confidence = Confidence.HIGH
    privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE


class PersonalMemoryCreate(BaseModel):
    memory_type: MemoryKind
    category: str = Field(min_length=1, max_length=100)
    key: str = Field(min_length=1, max_length=200)
    value: Any
    source: MemorySource = MemorySource.USER_EXPLICIT
    confidence: Confidence = Confidence.HIGH
    privacy_level: PrivacyLevel = PrivacyLevel.NORMAL
    retention: Retention = Retention.DURABLE


class ImportantDateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    date_value: str = Field(min_length=4, max_length=40)
    time_value: str | None = Field(default=None, max_length=20)
    date_type: str = Field(default="custom", max_length=50)
    person_id: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    confidence: Confidence = Confidence.HIGH
    privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE
