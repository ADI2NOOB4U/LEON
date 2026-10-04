"""
Tests for Skill Manifest and Skill Registry subsystem.
"""
import pytest
from backend.app.skills.schemas import SkillManifest, SkillParameter, SkillSafetyLevel
from backend.app.skills.registry import SkillRegistry


def test_skill_manifest_creation():
    manifest = SkillManifest(
        name="test_skill",
        version="1.0.0",
        display_name="Test Skill",
        description="A skill for testing",
        safety_level=SkillSafetyLevel.SAFE,
        tools=["test.tool"],
        parameters=[
            SkillParameter(name="param1", type="str", description="A string param", required=True)
        ],
    )
    assert manifest.name == "test_skill"
    assert len(manifest.parameters) == 1
    assert manifest.safety_level == SkillSafetyLevel.SAFE


def test_skill_registry_default_manifests():
    registry = SkillRegistry()
    skills = registry.list_skills()
    assert len(skills) >= 4

    names = [s.name for s in skills]
    assert "spotify" in names
    assert "browser" in names
    assert "desktop" in names


def test_skill_registry_register_and_get():
    registry = SkillRegistry()
    custom_manifest = SkillManifest(
        name="custom_calculator",
        version="0.1.0",
        display_name="Custom Calc",
        description="Math operations",
        safety_level=SkillSafetyLevel.SAFE,
        tools=["calc.add"],
    )
    registry.register_skill(custom_manifest)

    fetched = registry.get_skill("custom_calculator")
    assert fetched is not None
    assert fetched.name == "custom_calculator"

    # Verify tool lookup
    tool_skill = registry.get_skill_by_tool("calc.add")
    assert tool_skill is not None
    assert tool_skill.name == "custom_calculator"

