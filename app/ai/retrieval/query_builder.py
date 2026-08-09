"""Deterministic conversion of behavioral profiles into retrieval intent."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.behavior import BehavioralProfile


DEFAULT_MAX_INTERESTS = 5


@dataclass(frozen=True)
class RetrievalQuery:
    """Retrieval intent derived from a profile without exposing profile internals."""

    text: str
    interests_used: tuple[str, ...]
    sufficient_signal: bool


class BehavioralProfileQueryBuilder:
    """Build compact semantic retrieval queries from ranked profile interests."""

    def __init__(self, *, max_interests: int = DEFAULT_MAX_INTERESTS) -> None:
        if max_interests < 1:
            raise ValueError("max_interests must be at least 1")
        self.max_interests = max_interests

    def build(self, profile: BehavioralProfile) -> RetrievalQuery:
        """Return ordered, distinct interests when a profile has usable signal."""
        if profile.signal_strength <= 0.0 or not profile.interests:
            return RetrievalQuery(text="", interests_used=(), sufficient_signal=False)

        interests_used: list[str] = []
        seen: set[str] = set()
        for interest_score in profile.interests:
            interest = " ".join(interest_score.interest.split())
            canonical_interest = interest.casefold()
            if not canonical_interest or canonical_interest in seen:
                continue
            seen.add(canonical_interest)
            interests_used.append(interest)
            if len(interests_used) == self.max_interests:
                break

        if not interests_used:
            return RetrievalQuery(text="", interests_used=(), sufficient_signal=False)

        return RetrievalQuery(
            text=", ".join(interests_used),
            interests_used=tuple(interests_used),
            sufficient_signal=True,
        )
