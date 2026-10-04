"""
Tests for Evaluation Engine and Benchmarks.
"""
import asyncio
import pytest
from backend.app.evaluation.engine import EvaluationEngine
from backend.app.evaluation.benchmarks import BENCHMARK_ROUTING_CASES, BENCHMARK_SECURITY_CASES


def test_benchmarks_defined():
    assert len(BENCHMARK_ROUTING_CASES) >= 4
    assert len(BENCHMARK_SECURITY_CASES) >= 3


def test_evaluation_engine_run_benchmarks():
    engine = EvaluationEngine()
    scorecard = asyncio.run(engine.run_all_benchmarks())

    assert scorecard is not None
    assert scorecard.total_tests_run > 0
    assert scorecard.overall_score >= 0.0
    assert scorecard.routing_accuracy >= 0.0
    assert scorecard.security_pass_rate >= 0.0
    assert len(scorecard.results) > 0

    latest = engine.get_latest_scorecard()
    assert latest is not None
    assert latest.overall_score == scorecard.overall_score

