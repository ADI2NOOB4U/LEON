from __future__ import annotations

from typing import Dict, List, Optional
from backend.app.skills.schemas import SkillManifest, SkillParameter, SkillSafetyLevel


class SkillRegistry:
    """Registry and manager for extensible skills in LEON."""

    def __init__(self):
        self._skills: Dict[str, SkillManifest] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        spotify_skill = SkillManifest(
            id="skill_spotify",
            name="spotify",
            display_name="Spotify Music Controller",
            description="Playback control, search, and queue management for Spotify.",
            safety_level=SkillSafetyLevel.SAFE,
            tools=["media_control"],
            capabilities=["media.spotify"],
            parameters=[
                SkillParameter(name="action", type="str", description="play, pause, next, volume", required=True),
                SkillParameter(name="query", type="str", description="Search track or playlist name", required=False),
            ],
            risk_level="LOW",
        )
        self.register_skill(spotify_skill)

        browser_skill = SkillManifest(
            id="skill_browser",
            name="browser",
            display_name="Web Browser Operator",
            description="Safe web automation, search retrieval, and URL navigation.",
            safety_level=SkillSafetyLevel.SAFE,
            tools=["browser_open", "browser_extract"],
            capabilities=["browser.local", "research.current"],
            parameters=[
                SkillParameter(name="url", type="str", description="Target HTTP/HTTPS URL", required=True),
            ],
            risk_level="MEDIUM",
        )
        self.register_skill(browser_skill)

        desktop_skill = SkillManifest(
            id="skill_desktop",
            name="desktop",
            display_name="Computer Use & Desktop Agent",
            description="Observe desktop, diagnose visual error messages, and execute allowlisted UI actions.",
            safety_level=SkillSafetyLevel.CONFIRM,
            tools=["computer_observe", "computer_act", "computer_diagnose"],
            capabilities=["computer.observe", "computer.act", "computer.diagnose"],
            risk_level="HIGH",
        )
        self.register_skill(desktop_skill)

        coding_skill = SkillManifest(
            id="skill_coding",
            name="coding",
            display_name="Coding & Self-Repair Agent",
            description="Workspace code generation, execution, testing, and autonomous self-repair.",
            safety_level=SkillSafetyLevel.CONFIRM,
            tools=["coding_execute", "fs_read", "fs_write"],
            capabilities=["coding.local", "tasks.autonomous"],
            risk_level="HIGH",
        )
        self.register_skill(coding_skill)

    def register_skill(self, manifest: SkillManifest) -> None:
        self._skills[manifest.name] = manifest

    def get_skill(self, name: str) -> Optional[SkillManifest]:
        return self._skills.get(name)

    def list_skills(self) -> List[SkillManifest]:
        return list(self._skills.values())

    def get_skill_by_tool(self, tool_name: str) -> Optional[SkillManifest]:
        for skill in self._skills.values():
            if tool_name in skill.tools:
                return skill
        return None


skill_registry = SkillRegistry()
default_skills = skill_registry

