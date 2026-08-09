"""Deterministic recommendation prompt construction."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.ai.retrieval.retriever import RetrievedProduct
from app.schemas.behavior import BehavioralProfile


MAX_PROFILE_INTERESTS = 5
MAX_PROFILE_EVIDENCE = 5


@dataclass(frozen=True)
class RecommendationPrompt:
    """Provider-neutral system and user content for recommendation generation."""

    system: str
    user: str


SYSTEM_PROMPT = """You generate concise, personalized SmartReco recommendations.
The behavioral profile describes the user's demonstrated interests. The supplied catalog
candidates are the only products you may select. Every selected product_id must exactly
match a supplied candidate ID. Do not invent products, IDs, titles, categories, prices,
capabilities, or claims unsupported by the supplied product descriptions. Make the copy
personalized and persuasive, with a user-specific reason for every selected product.
Return only one JSON object with this exact shape:
{"narrative": "concise personalized summary", "recommendations": [{"product_id": "UUID", "reason": "user-specific reason"}]}
"""


def build_recommendation_prompt(
    profile: BehavioralProfile,
    retrieved_products: list[RetrievedProduct],
) -> RecommendationPrompt:
    """Build compact, deterministic context from frozen behavior and catalog contracts."""
    payload = {
        "behavioral_profile": {
            "interests": [
                {"interest": interest.interest, "score": interest.score}
                for interest in profile.interests[:MAX_PROFILE_INTERESTS]
            ],
            "evidence": [
                {
                    "interest": evidence.interest,
                    "event_type": evidence.event_type.value,
                    "source": evidence.source,
                }
                for evidence in profile.evidence[:MAX_PROFILE_EVIDENCE]
            ],
            "recent_activity": {
                "total_events": profile.recent_activity.total_events,
                "product_views": profile.recent_activity.product_views,
                "searches": profile.recent_activity.searches,
                "clicks": profile.recent_activity.clicks,
                "time_spent_seconds": profile.recent_activity.time_spent_seconds,
            },
            "signal_strength": profile.signal_strength,
        },
        "catalog_candidates": [
            {
                "product_id": str(product.product_id),
                "title": product.title,
                "description": product.description,
                "category": product.category,
                "price": format(product.price, "f"),
            }
            for product in retrieved_products
        ],
    }
    return RecommendationPrompt(
        system=SYSTEM_PROMPT,
        user=json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
    )
