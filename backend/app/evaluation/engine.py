from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import statistics
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.core.action_authority import ActionAuthority
from backend.app.evaluation.benchmarks import BenchmarkCase, DEFAULT_BENCHMARK_CASES
from backend.app.intelligence import intelligence_core
from backend.app.memory.knowledge import knowledge_service
from backend.app.security.kernel import security_kernel
from backend.app.tools.system_tools import system_registry


class EvaluationScorecard(BaseModel):
    timestamp: str
    routing_accuracy_pct: float
    tool_success_rate_pct: float
    security_pass_rate_pct: float
    memory_relevance_rate_pct: float
    verification_success_rate_pct: float
    median_routing_ms: float
    p95_routing_ms: float
    total_tests_run: int
    passed_tests: int
    details: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def overall_score(self) -> float:
        return round((self.routing_accuracy_pct + self.tool_success_rate_pct + self.security_pass_rate_pct + self.memory_relevance_rate_pct) / 4, 1)

    @property
    def routing_accuracy(self) -> float:
        return self.routing_accuracy_pct

    @property
    def security_pass_rate(self) -> float:
        return self.security_pass_rate_pct

    @property
    def results(self) -> List[Dict[str, Any]]:
        return self.details


class EvaluationEngine:
    """Automated evaluation and benchmark suite generator for LEON."""

    def __init__(self, cases: Optional[List[BenchmarkCase]] = None):
        self.cases = cases or DEFAULT_BENCHMARK_CASES
        self._last_scorecard: Optional[EvaluationScorecard] = None

    async def run_evaluation(self) -> EvaluationScorecard:
        details = []
        routing_latencies: List[float] = []
        routing_passed = 0
        routing_total = 0

        sec_passed = 0
        sec_total = 0

        tool_passed = 0
        tool_total = 0

        mem_passed = 0
        mem_total = 0

        authority = ActionAuthority(system_registry)

        for case in self.cases:
            # 1. Routing Benchmarks
            if case.category == "routing":
                routing_total += 1
                start = time.perf_counter()
                decision = intelligence_core.route(case.input)
                elapsed_ms = (time.perf_counter() - start) * 1000
                routing_latencies.append(elapsed_ms)

                is_correct = (decision.route == case.expected_route)
                if is_correct:
                    routing_passed += 1
                details.append({
                    "case_id": case.id,
                    "category": case.category,
                    "passed": is_correct,
                    "expected": case.expected_route,
                    "actual": decision.route,
                    "latency_ms": round(elapsed_ms, 3),
                })

            # 2. Security Benchmarks
            elif case.category == "security":
                sec_total += 1
                is_inj, reason = security_kernel.detect_prompt_injection(case.input)
                if case.should_block:
                    passed = is_inj
                else:
                    passed = not is_inj

                if passed:
                    sec_passed += 1
                details.append({
                    "case_id": case.id,
                    "category": case.category,
                    "passed": passed,
                    "blocked": is_inj,
                    "reason": reason,
                })

            # 3. Tool Benchmarks
            elif case.category == "tool":
                tool_total += 1
                try:
                    res = await authority.execute(case.input, {})
                    passed = isinstance(res, dict) and bool(res)
                except Exception:
                    passed = False

                if passed:
                    tool_passed += 1
                details.append({
                    "case_id": case.id,
                    "category": case.category,
                    "passed": passed,
                    "tool": case.input,
                })

            # 4. Memory Relevance Benchmarks
            elif case.category == "memory":
                mem_total += 1
                should_ret = knowledge_service.should_retrieve_memory(case.input)
                expected = (case.id == "mem_1")
                passed = (should_ret == expected)
                if passed:
                    mem_passed += 1
                details.append({
                    "case_id": case.id,
                    "category": case.category,
                    "passed": passed,
                    "retrieved": should_ret,
                    "expected": expected,
                })

        # Calculate metrics
        routing_latencies.sort()
        count = len(routing_latencies)
        median_lat = statistics.median(routing_latencies) if count else 0.0
        p95_idx = min(int(0.95 * count), count - 1)
        p95_lat = routing_latencies[p95_idx] if count else 0.0

        total_tests = routing_total + sec_total + tool_total + mem_total
        passed_tests = routing_passed + sec_passed + tool_passed + mem_passed

        scorecard = EvaluationScorecard(
            timestamp=datetime.now(timezone.utc).isoformat(),
            routing_accuracy_pct=round((routing_passed / max(routing_total, 1)) * 100, 1),
            tool_success_rate_pct=round((tool_passed / max(tool_total, 1)) * 100, 1),
            security_pass_rate_pct=round((sec_passed / max(sec_total, 1)) * 100, 1),
            memory_relevance_rate_pct=round((mem_passed / max(mem_total, 1)) * 100, 1),
            verification_success_rate_pct=100.0 if passed_tests == total_tests else round((passed_tests / total_tests) * 100, 1),
            median_routing_ms=round(median_lat, 3),
            p95_routing_ms=round(p95_lat, 3),
            total_tests_run=total_tests,
            passed_tests=passed_tests,
            details=details,
        )

        self._last_scorecard = scorecard
        return scorecard

    async def run_all_benchmarks(self) -> EvaluationScorecard:
        return await self.run_evaluation()

    def get_last_scorecard(self) -> Optional[EvaluationScorecard]:
        return self._last_scorecard

    def get_latest_scorecard(self) -> Optional[EvaluationScorecard]:
        return self._last_scorecard


evaluation_engine = EvaluationEngine()

