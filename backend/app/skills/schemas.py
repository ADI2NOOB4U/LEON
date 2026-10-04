from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillParameter(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Optional[Any] = None


class SkillSafetyLevel(StrEnum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class SkillManifest(BaseModel):
    id: str = ""
    version: str = "1.0.0"
    name: str
    description: str
    display_name: str = ""
    safety_level: SkillSafetyLevel = SkillSafetyLevel.CONFIRM
    tools: List[str] = Field(default_factory=list)
    parameters: List[SkillParameter] = Field(default_factory=list)
    author: str = "LEON Core"
    capabilities: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=lambda: ["CONFIRM"])
    risk_level: str = "MEDIUM"
    inputs: List[SkillParameter] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    providers: List[str] = Field(default_factory=list)
    verifier: str = "result"
    enabled: bool = True

