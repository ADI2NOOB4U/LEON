from .schemas import RouteCandidate


def rank(candidates: list[RouteCandidate]) -> list[RouteCandidate]:
    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
