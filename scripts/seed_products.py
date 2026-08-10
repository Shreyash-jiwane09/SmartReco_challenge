"""Seed the approved professional e-learning catalog through ProductService."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.session import SessionLocal
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate
from app.services.product import ProductService
from app.services.vector_service import ProductVectorService


@dataclass(frozen=True)
class CatalogCourse:
    """One approved catalog item without persistence-owned fields."""

    title: str
    category: str
    price: Decimal
    description: str
    is_active: bool = True

    def as_create(self) -> ProductCreate:
        return ProductCreate(
            title=self.title,
            category=self.category,
            price=self.price,
            description=self.description,
            is_active=self.is_active,
        )


CATALOG: tuple[CatalogCourse, ...] = (
    CatalogCourse("Building Production AI Agents with LangGraph", "Data Science & AI", Decimal("74.99"), "Build stateful AI agents using LangGraph with explicit nodes, conditional routing, tool execution, state management, and grounded retrieval. The course focuses on designing reliable agent workflows that can be integrated into production AI applications."),
    CatalogCourse("Agentic AI Systems: From Reasoning to Tool Use", "Data Science & AI", Decimal("64.99"), "Explore how modern AI agents plan, reason over context, invoke tools, maintain state, and complete multi-step tasks. Learners design agent architectures that balance autonomy with predictable application behavior."),
    CatalogCourse("Multi-Agent Systems for Collaborative AI Workflows", "Data Science & AI", Decimal("79.99"), "Design applications where specialized AI agents coordinate responsibilities, exchange structured information, and complete complex workflows. The course covers orchestration patterns, delegation, shared state, failure boundaries, and practical multi-agent design."),
    CatalogCourse("Retrieval-Augmented Generation for Knowledge Applications", "Data Science & AI", Decimal("59.99"), "Build grounded LLM applications that retrieve relevant knowledge before generating responses. Topics include document representation, embeddings, vector search, retrieval quality, context construction, and reducing hallucination through grounded generation."),
    CatalogCourse("LLM Application Engineering in Python", "Data Science & AI", Decimal("69.99"), "Develop production-oriented applications around large language models using Python, structured prompts, API integration, validation, retries, and application-layer safeguards. The focus is on engineering reliable AI features rather than isolated prompt experiments."),
    CatalogCourse("Prompt Engineering for Reliable AI Applications", "Data Science & AI", Decimal("34.99"), "Learn practical prompt design for structured generation, reasoning tasks, information extraction, classification, and grounded responses. The course emphasizes repeatability, clear constraints, context management, and evaluation rather than prompt tricks."),
    CatalogCourse("Evaluating and Testing Generative AI Systems", "Data Science & AI", Decimal("54.99"), "Create evaluation strategies for AI applications using representative test sets, qualitative criteria, structured outputs, retrieval checks, and regression testing. Learn to identify failure modes before generative features reach production users."),
    CatalogCourse("Machine Learning Foundations with Python", "Data Science & AI", Decimal("44.99"), "Build a practical foundation in supervised and unsupervised machine learning using Python. Work through feature preparation, model training, validation, classification, regression, clustering, and responsible interpretation of model performance."),
    CatalogCourse("Production Backend Development with FastAPI", "Technology & Software", Decimal("49.99"), "Build maintainable Python APIs with FastAPI using request validation, dependency injection, layered architecture, exception handling, authentication, and automated testing. The course moves from API fundamentals to production-oriented backend design."),
    CatalogCourse("Modern Python for Backend Engineers", "Technology & Software", Decimal("39.99"), "Strengthen Python skills needed for professional backend development, including typing, dataclasses, exception design, modules, iterators, testing practices, and maintainable application structure. Examples focus on server-side application development."),
    CatalogCourse("PostgreSQL for Application Developers", "Technology & Software", Decimal("39.99"), "Learn relational database design and PostgreSQL from the perspective of application development. Cover schemas, relationships, indexing, transactions, query planning, constraints, and patterns for integrating PostgreSQL safely into backend services."),
    CatalogCourse("Designing Secure REST APIs", "Technology & Software", Decimal("44.99"), "Design APIs with authentication, authorization, input validation, secure error handling, rate-conscious architecture, and clear HTTP semantics. The course examines common API security weaknesses and practical safeguards for production services."),
    CatalogCourse("React Interfaces for Modern Web Applications", "Technology & Software", Decimal("39.99"), "Build component-based web interfaces using React, reusable UI composition, state management, forms, data fetching, and client-side interaction patterns. The course is aimed at developers who need to create maintainable application frontends."),
    CatalogCourse("Software Testing with Python and Pytest", "Technology & Software", Decimal("29.99"), "Write maintainable automated tests for Python applications using pytest, fixtures, parametrization, mocking, integration tests, and regression strategies. Learn how focused test suites support safe application evolution."),
    CatalogCourse("Docker for Application Delivery", "Cloud & DevOps", Decimal("34.99"), "Containerize backend and web applications with Docker using reproducible images, environment configuration, volumes, networking, and Compose-based development environments. The course emphasizes practical deployment readiness rather than isolated Docker commands."),
    CatalogCourse("CI/CD Pipelines with GitHub Actions", "Cloud & DevOps", Decimal("39.99"), "Automate validation, testing, packaging, and deployment workflows using GitHub Actions. Build pipelines that protect branches, manage secrets, run quality checks, and provide repeatable delivery for modern software projects."),
    CatalogCourse("AWS Foundations for Application Engineers", "Cloud & DevOps", Decimal("44.99"), "Understand core AWS services used to run web applications, including compute, storage, networking, IAM, managed databases, and deployment considerations. The course connects cloud concepts to practical application architecture."),
    CatalogCourse("Python Data Analysis with Pandas", "Data Analytics", Decimal("29.99"), "Analyze structured datasets with Pandas using filtering, transformation, grouping, missing-data handling, aggregation, reshaping, and time-aware operations. The course develops a practical workflow for turning raw tabular data into useful analytical results."),
    CatalogCourse("SQL for Analytical Decision Making", "Data Analytics", Decimal("24.99"), "Use SQL to investigate business and operational data through joins, aggregations, subqueries, common table expressions, window functions, and analytical reporting patterns. Exercises focus on answering real decision-oriented questions from relational data."),
    CatalogCourse("Data Visualization with Python", "Data Analytics", Decimal("29.99"), "Turn analytical results into understandable visual stories using Python plotting libraries. Learn chart selection, comparative analysis, distributions, trends, annotations, and practices for communicating data accurately to technical and business audiences."),
    CatalogCourse("Excel Analytics for Business Professionals", "Data Analytics", Decimal("19.99"), "Use modern spreadsheet techniques for cleaning, analyzing, summarizing, and presenting business data. The course covers formulas, lookup patterns, pivot-based analysis, structured tables, and practical reporting workflows."),
    CatalogCourse("Product Management for Digital Products", "Business & Management", Decimal("39.99"), "Learn how digital products move from customer problems to prioritized roadmaps and measurable outcomes. Topics include discovery, requirement framing, stakeholder communication, prioritization, experimentation, and product metrics."),
    CatalogCourse("Agile Project Leadership and Delivery", "Business & Management", Decimal("29.99"), "Manage iterative projects using practical Agile planning, backlog prioritization, estimation, delivery reviews, risk management, and stakeholder communication. The course focuses on leading teams toward reliable outcomes without excessive process overhead."),
    CatalogCourse("Digital Marketing Strategy and Campaign Planning", "Marketing", Decimal("29.99"), "Design integrated digital campaigns by connecting audience research, positioning, content, channel selection, conversion goals, and performance measurement. Learn to create marketing plans that can be evaluated and improved using real campaign data."),
    CatalogCourse("SEO and Content Discovery Fundamentals", "Marketing", Decimal("24.99"), "Understand how search intent, site structure, useful content, keywords, and technical foundations influence organic discoverability. The course focuses on sustainable search visibility and content planning rather than shortcuts or ranking guarantees."),
    CatalogCourse("UX Design for Web and Mobile Products", "Design & Creativity", Decimal("34.99"), "Design usable digital experiences through user research, information architecture, interaction flows, wireframes, and iterative usability testing. Learners connect user needs with clear interface decisions and product goals."),
    CatalogCourse("Visual Design Systems for Digital Products", "Design & Creativity", Decimal("29.99"), "Create consistent product interfaces through typography, spacing, layout, reusable components, visual hierarchy, and design-system thinking. The course helps designers build coherent visual languages that scale across screens and features."),
    CatalogCourse("Financial Analysis for Business Decisions", "Finance & Accounting", Decimal("34.99"), "Develop practical financial literacy through income statements, balance sheets, cash-flow analysis, ratios, budgeting, and investment-oriented decision concepts. The course is designed for professionals who need to interpret financial information rather than perform specialist accounting."),
    CatalogCourse("Leadership Communication for Technical Professionals", "Personal Development", Decimal("24.99"), "Communicate technical ideas clearly to colleagues, managers, and non-technical stakeholders. Practice structured explanations, decision communication, feedback, meeting leadership, and adapting detail to different audiences."),
    CatalogCourse("Focus, Planning and Sustainable Productivity", "Personal Development", Decimal("19.99"), "Build practical systems for prioritizing meaningful work, planning realistic workloads, managing interruptions, and reviewing progress. The course emphasizes sustainable professional productivity rather than short-term motivational techniques."),
)


@dataclass(frozen=True)
class SeedResult:
    """A concise summary of one catalog seed run."""

    created: int
    skipped: int


def _duplicate_key(title: str, category: str) -> tuple[str, str]:
    return (title.strip().casefold(), category.strip().casefold())


def seed_catalog(
    repository: ProductRepository,
    service: ProductService,
    *,
    output: Callable[[str], None] = print,
    catalog: Iterable[CatalogCourse] = CATALOG,
) -> SeedResult:
    """Create missing catalog items through the established dual-write service."""
    existing_keys = {
        _duplicate_key(product.title, product.category)
        for product in repository.list(limit=1000)
    }
    created = 0
    skipped = 0
    for course in catalog:
        key = _duplicate_key(course.title, course.category)
        if key in existing_keys:
            output(f"Skipped duplicate: {course.title}")
            skipped += 1
            continue
        service.create_product(course.as_create())
        existing_keys.add(key)
        output(f"Created: {course.title}")
        created += 1
    return SeedResult(created=created, skipped=skipped)


def main() -> None:
    """Run the approved catalog seed against the configured application database."""
    session = SessionLocal()
    try:
        repository = ProductRepository(session)
        service = ProductService(repository, ProductVectorService.from_settings())
        result = seed_catalog(repository, service)
        print("\nCatalog seed complete.")
        print(f"Created: {result.created}")
        print(f"Skipped: {result.skipped}")
        print(f"Total catalog definitions: {len(CATALOG)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
