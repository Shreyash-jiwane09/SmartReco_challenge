"""Unit coverage for the release catalog seed helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from collections import Counter


SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "seed_products.py"
SPEC = importlib.util.spec_from_file_location("seed_products", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
seed_products = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = seed_products
SPEC.loader.exec_module(seed_products)


class _Repository:
    def __init__(self, products: list[object]) -> None:
        self.products = products
        self.limits: list[int | None] = []

    def list(self, *, offset: int = 0, limit: int | None = None) -> list[object]:
        self.limits.append(limit)
        return self.products


class _Service:
    def __init__(self) -> None:
        self.created: list[object] = []

    def create_product(self, payload: object) -> None:
        self.created.append(payload)


def test_catalog_has_the_approved_size_distribution_and_active_decimal_prices() -> None:
    assert len(seed_products.CATALOG) == 30
    assert Counter(course.category for course in seed_products.CATALOG) == {
        "Data Science & AI": 8,
        "Technology & Software": 6,
        "Cloud & DevOps": 3,
        "Data Analytics": 4,
        "Business & Management": 2,
        "Marketing": 2,
        "Design & Creativity": 2,
        "Finance & Accounting": 1,
        "Personal Development": 2,
    }
    assert all(course.is_active for course in seed_products.CATALOG)
    assert all(course.price.as_tuple().exponent == -2 for course in seed_products.CATALOG)


def test_seed_catalog_skips_normalized_existing_and_same_run_duplicates() -> None:
    catalog = (
        seed_products.CatalogCourse("  Course One ", "Data", seed_products.Decimal("19.99"), "First."),
        seed_products.CatalogCourse("course one", " data ", seed_products.Decimal("19.99"), "Duplicate."),
        seed_products.CatalogCourse("Course Two", "Data", seed_products.Decimal("24.99"), "Second."),
    )
    repository = _Repository([SimpleNamespace(title="COURSE ONE", category="DATA")])
    service = _Service()
    messages: list[str] = []

    result = seed_products.seed_catalog(repository, service, catalog=catalog, output=messages.append)

    assert repository.limits == [1000]
    assert result == seed_products.SeedResult(created=1, skipped=2)
    assert [payload.title for payload in service.created] == ["Course Two"]
    assert messages == [
        "Skipped duplicate:   Course One ",
        "Skipped duplicate: course one",
        "Created: Course Two",
    ]
