from __future__ import annotations

import re
import time
from typing import Any

from backend.app.core.capabilities import classify_command, is_datetime_request, is_system_state_request, is_weather_request
from backend.app.core.router import ModelRouter
from backend.app.security.cloud_privacy import is_safe_public_cloud_text
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.system_tools import system_registry

from .metrics import RouteMetrics
from .registry import CapabilityRegistry, CapabilitySpec
from .schemas import Intent, RequestKind, RouteCandidate, RouteDecision


class RouterProvider:
    def classify(self, message: str) -> Intent | None:
        return None


class IntelligenceCore:
    def __init__(self, registry: CapabilityRegistry | None = None,
                 tools: ToolRegistry | None = None, metrics: RouteMetrics | None = None):
        self.registry = registry or CapabilityRegistry()
        self.tools = tools or system_registry
        self.metrics = metrics or RouteMetrics()

    @staticmethod
    def _privacy(message: str) -> str:
        return "public" if is_safe_public_cloud_text(message) else "private"

    def _intent(self, message: str) -> Intent:
        value = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9']+", " ", (message or "").strip().lower())).strip()
        proposal = classify_command(message)
        privacy = self._privacy(message)
        if is_datetime_request(message):
            return Intent(intent="datetime.current", confidence=.99, capability="system.datetime", action="current", kind=RequestKind.SIMPLE, privacy_class="local")
        if is_system_state_request(message):
            return Intent(intent="system.state", confidence=.98, capability="system.state", action="status", kind=RequestKind.SIMPLE, privacy_class="local")
        if is_weather_request(message):
            return Intent(intent="weather.current", confidence=.98, capability="weather.current", action="current", kind=RequestKind.SIMPLE, privacy_class="public")
        if proposal.capability.value == "EMAIL":
            return Intent(intent="email.send", confidence=.97, capability="email.local", action="send", kind=RequestKind.ACTION, requires_confirmation=True, privacy_class="private")
        if re.search(r"\b(?:what(?:'s| is) my cpu|cpu usage|memory usage|disk usage|system stats)\b", value):
            return Intent(intent="system.stats", confidence=.97, capability="system.stats", action="current", kind=RequestKind.SIMPLE)
        if re.search(r"\b(?:forget|delete|remove)\b.*\b(?:memory|that|my name|my preference|him|her|them)\b", value):
            return Intent(intent="memory.delete", confidence=.98, capability="memory.local", action="delete", kind=RequestKind.ACTION, needs_memory=True, privacy_class="private")
        if re.search(r"\b(?:remember|don't forget|do not forget)\b", value) or re.search(r"\bmy (?:name|preferred name) is\b", value) or re.search(r"\bis my (?:partner|girlfriend|boyfriend|friend|mentor|colleague)\b", value):
            return Intent(intent="memory.store", confidence=.98, capability="memory.local", action="store", kind=RequestKind.ACTION, needs_memory=True, privacy_class="private")
        if re.search(r"\b(?:what did i (?:call|tell you|say)|do you remember|what is my project)\b", value):
            return Intent(intent="memory.retrieve", confidence=.94, capability="memory.local", action="retrieve", kind=RequestKind.ACTION, needs_memory=True, privacy_class="private")
        if re.search(r"\bremind me\b", value) and re.search(r"\b(?:birthday|anniversary|deadline|important date|week before|days before)\b", value):
            return Intent(intent="memory.reminder", confidence=.96, capability="memory.local", action="schedule", kind=RequestKind.ACTION, needs_memory=True, privacy_class="private")
        if re.search(r"\bfind\b.*\b(?:about|on)\b.*\bai\b", value):
            return Intent(intent="research.current", confidence=.72, capability="research.current", action="research", kind=RequestKind.ACTION, needs_web=True, privacy_class="public")
        if re.search(r"\b(?:create|build|make)\b.*\b(?:project|app)\b.*\b(?:run|test|fix)\b", value) or value.count(",") >= 2:
            return Intent(intent="task.autonomous", confidence=.93, capability="tasks.autonomous", action="create", kind=RequestKind.TASK, needs_memory=False, privacy_class="private", requires_confirmation=True)
        if proposal.capability.value == "MEDIA":
            changes_playback = proposal.action in {"play", "pause", "resume", "stop", "next", "previous", "volume"}
            ambiguous = proposal.action == "play" and bool(re.search(r"\b(?:play|start|put on|listen to)\s+(?:something|anything|a song|music)?\s*$", value))
            return Intent(intent=f"media.{proposal.action}", confidence=.58 if ambiguous else .98, capability="media.spotify", action=proposal.action, kind=RequestKind.ACTION, entities={"query": message}, requires_confirmation=changes_playback, privacy_class="private")
        if re.search(r"\b(?:what(?:'s| is) wrong on (?:my )?screen|why (?:are|is) (?:my )?(?:tests?|code) failing|diagnose (?:the )?screen|look at (?:this )?error|fix (?:this|the) error)\b", value):
            return Intent(intent="computer.diagnose", confidence=.98, capability="computer.diagnose", action="diagnose", kind=RequestKind.ACTION, needs_vision=True, privacy_class="private")
        if re.search(r"\b(?:what application am i using|what app is (?:open|active)|what(?:'s| is) (?:the )?active (?:app|window)|active application)\b", value):
            return Intent(intent="computer.observe", confidence=.96, capability="computer.observe", action="active_app", kind=RequestKind.SIMPLE, privacy_class="private")
        if re.search(r"\b(?:click (?:the|on)|type (?:into|text)|press (?:ctrl|alt|shift|key))\b", value):
            return Intent(intent="computer.act", confidence=.95, capability="computer.act", action="execute", kind=RequestKind.ACTION, requires_confirmation=True, privacy_class="private")
        if proposal.capability.value in {"SCREEN", "OCR"} or re.search(r"\b(?:what(?:'s| is) on|look at) (?:my )?screen\b", value):
            return Intent(intent="screen.analyze", confidence=.97, capability="screen.local", action=proposal.action, kind=RequestKind.ACTION, needs_vision=True, privacy_class="private")
        if proposal.capability.value == "RESEARCH":
            return Intent(intent="research.current", confidence=.96, capability="research.current", action="research", kind=RequestKind.ACTION, needs_web=True, privacy_class="public" if privacy == "public" else "private")
        if proposal.capability.value == "CODING" or re.search(r"\b(?:write|create)\b.*\b(?:python|function|script|code)\b", value):
            return Intent(intent="coding.request", confidence=.91, capability="coding.local", action="execute", kind=RequestKind.ACTION, requires_confirmation=True, privacy_class="private")
        if proposal.capability.value == "SYSTEM" and proposal.action == "open":
            return Intent(intent="desktop.open", confidence=.94, capability="desktop.applications", action="open", kind=RequestKind.ACTION, requires_confirmation=True, privacy_class="private", entities={"app": message})
        if re.fullmatch(r"(?:hi|hello|hey)(?: leon)?|(?:what|who) are you", value):
            return Intent(intent="chat.general", confidence=.99, capability="chat.general", action="chat", kind=RequestKind.CHAT)
        if proposal.capability.value == "BROWSER":
            return Intent(intent="browser.navigate", confidence=.88, capability="browser.local", action=proposal.action, kind=RequestKind.ACTION, requires_confirmation=True, privacy_class="public")
        return Intent(intent="chat.general", confidence=.62, capability="chat.general", action="chat", kind=RequestKind.CHAT, privacy_class=privacy)

    def _available(self, spec: CapabilitySpec) -> bool:
        if spec.id == "media.spotify":
            # MediaManager performs the authoritative provider discovery at execution time.
            return True
        return self.registry.availability(spec, self.tools)

    def route(self, message: str, context: dict[str, Any] | None = None) -> RouteDecision:
        started = time.perf_counter()
        intent = self._intent(message)
        spec = self.registry.get(intent.capability) or self.registry.get("chat.general")
        assert spec is not None
        candidates: list[RouteCandidate] = []
        for candidate_spec in self.registry.list():
            available = self._available(candidate_spec)
            score = 0.02
            reasons: list[str] = []
            if candidate_spec.id == intent.capability:
                score += .90 * intent.confidence; reasons.append("capability matched")
            if candidate_spec.privacy_class in {"local", "private"} and intent.privacy_class == "private":
                score += .08; reasons.append("private data stays local")
            if candidate_spec.id == "research.current" and intent.needs_web:
                score += .1; reasons.append("current-information signal")
            if candidate_spec.id == "chat.general" and intent.kind == RequestKind.CHAT:
                score += .1; reasons.append("conversation fallback")
            if candidate_spec.id != intent.capability:
                score *= intent.confidence
            if not available:
                score = 0
                reasons.append("provider/tool unavailable")
            candidates.append(RouteCandidate(route=candidate_spec.id, score=min(score, 1), provider=candidate_spec.provider, available=available, explanation=reasons))
        candidates.sort(key=lambda item: item.score, reverse=True)
        selected = candidates[0] if candidates else RouteCandidate(route="chat.general", score=.1, provider="local")
        selected_spec = self.registry.get(selected.route) or spec
        elapsed = (time.perf_counter() - started) * 1000
        decision = RouteDecision(intent=intent, route=selected.route, provider=selected.provider,
            confidence=selected.score, candidates=candidates[:6], requires_confirmation=intent.requires_confirmation or selected_spec.confirmation,
            permission="CONFIRM" if intent.requires_confirmation or selected_spec.confirmation else "SAFE",
            needs_web=intent.needs_web, needs_vision=intent.needs_vision, needs_memory=intent.needs_memory,
            model_role=selected_spec.model_role, fallback_route="chat.general" if selected.route != "chat.general" else None,
            explanation=selected.explanation + [f"deterministic route in {elapsed:.2f}ms"], routing_ms=elapsed)
        self.metrics.record(intent=intent.name, route=decision.route, confidence=decision.confidence, provider=decision.provider, latency_ms=elapsed, confirmation_required=decision.requires_confirmation)
        return decision

    def record_execution(self, decision: RouteDecision, *, success: bool,
                         verification_result: bool | None = None,
                         fallback_used: bool = False) -> None:
        self.metrics.record(intent=decision.intent.name, route=decision.route,
                            confidence=decision.confidence, provider=decision.provider,
                            success=success, latency_ms=decision.routing_ms,
                            fallback_used=fallback_used,
                            confirmation_required=decision.requires_confirmation,
                            verification_result=verification_result)


intelligence_core = IntelligenceCore()
