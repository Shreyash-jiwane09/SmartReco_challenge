"""Application metadata used by the FastAPI application."""

APP_TITLE = "SmartReco"

APP_DESCRIPTION = (
    "Enterprise Behavioral AI Recommendation Platform built for the "
    "SmartReco Build Challenge 2026."
)

APP_VERSION = "0.1.0"

OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": "Authentication and access-token operations.",
    },
    {
        "name": "Users",
        "description": "User account and profile operations.",
    },
    {
        "name": "Products",
        "description": "Product catalog operations.",
    },
    {
        "name": "Events",
        "description": "User event and interaction operations.",
    },
    {
        "name": "Recommendations",
        "description": "Personalized recommendation operations.",
    },
    {
        "name": "Admin",
        "description": "Administrative and platform management operations.",
    },
    {
        "name": "Health",
        "description": "Application health and readiness operations.",
    },
]
