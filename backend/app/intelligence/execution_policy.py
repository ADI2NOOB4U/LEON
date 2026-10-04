from .schemas import RouteDecision


def can_auto_execute(decision: RouteDecision) -> bool:
    return decision.permission == "SAFE" and decision.confidence >= .9
