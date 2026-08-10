# SmartReco

SmartReco is a behavioral AI recommendation platform built for the SmartReco Build Challenge 2026. It turns authenticated browsing activity into evolving interest profiles, retrieves relevant catalog products semantically, and produces catalog-grounded recommendations.

## What SmartReco Does

Users browse a Jinja-powered product catalog while the browser records product views, searches, clicks, and time spent. Events are batched and ingested without blocking normal browsing. The backend derives a `BehavioralProfile`, applies trigger and cooldown rules, retrieves products through Mesh embeddings and ChromaDB, grounds them against PostgreSQL, and uses a LangGraph workflow plus Mesh Chat to generate and persist recommendations.

Unlike static “related product” widgets, SmartReco responds to meaningful changes in a user's behavior while avoiding generation on every interaction.

## Professional Learning Catalog

SmartReco includes a 30-course, multi-domain professional e-learning catalog. Course titles and descriptions form meaningful AI, backend, and data semantic neighborhoods, while realistic cross-domain courses provide useful retrieval distractors. Catalog products are seeded through `ProductService`, which synchronizes PostgreSQL and ChromaDB.

## Challenge Requirement Coverage

| Requirement | Status |
| --- | --- |
| Email/password authentication and User/Admin roles | Complete |
| Authenticated product browsing, search, and detail | Complete |
| Recommendation page and refresh UX | Complete |
| Admin product create, update, and delete | Complete |
| Product SQL + ChromaDB synchronization | Complete |
| Batched behavioral tracking (`PRODUCT_VIEW`, `SEARCH`, `CLICK`, `TIME_SPENT`) | Complete |
| Behavioral intelligence, trigger, and cooldown | Complete |
| Semantic retrieval and PostgreSQL catalog grounding | Complete |
| Mesh API recommendation generation | Complete |
| Recommendation persistence | Complete |
| Efficient trigger-controlled AI generation | Complete |
| Dockerized execution | Verified Dockerfile + Docker Compose for FastAPI, PostgreSQL, explicit migrations, persistent PostgreSQL/Chroma data, and catalog seeding |

### Bonus feature status

- **LangGraph — VERIFIED.** The explicit recommendation workflow runs
  `prepare_context` → `generate_recommendation` → `validate_grounding`.
- **Retrieval polish — VERIFIED.** Chroma retrieval filters to active-product
  metadata, then PostgreSQL re-grounds candidates and rejects invalid, stale,
  or inactive products. This is not reranking, hybrid search, or graph
  retrieval.
- **LangSmith — IMPLEMENTED / LIVE VERIFICATION PENDING.** Optional tracing records
  recommendation workflow visibility in the `smartreco-build-challenge-2026`
  trace project when configured; normal operation remains silent when tracing
  is disabled.
- **Scheduled proactive delivery — IMPLEMENTED / LIVE VERIFICATION PENDING.**
  APScheduler runs the existing recommendation service for eligible users and
  sends SMTP digests from persisted, catalog-grounded recommendations.
  The scheduler and SMTP path are covered by automated tests; no live
  scheduler-to-email delivery evidence is stored in this repository.

## Architecture

```text
Browser / Jinja UI
        ↓
FastAPI → batched behavioral events → PostgreSQL
        ↓
BehavioralProfile → trigger / cooldown
        ↓
Mesh embeddings → ChromaDB semantic retrieval
        ↓
PostgreSQL catalog grounding
        ↓
LangGraph + Mesh Chat
        ↓
Grounded recommendation persistence → recommendation UI
```

Admin product mutations follow a parallel dual-write path:

```text
Admin UI → ProductService → PostgreSQL + ChromaDB synchronization
```

## Technology Stack

- FastAPI, Jinja2, JavaScript
- PostgreSQL, SQLAlchemy, Alembic
- ChromaDB
- Mesh API
- LangGraph
- Docker, Docker Compose
- GitHub Actions

## Docker Quick Start

Option A — Docker Setup is the recommended reproducible path for evaluators.
It runs the FastAPI/Jinja2 application and PostgreSQL in Compose; Chroma is
embedded in `app` and persisted in a named volume. Migrations and catalog
seeding are explicit release operations.

### 1. Clone

```bash
git clone <repository-url>
cd smartreco
```

### 2. Configure environment

Create `.env` from the supplied template:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# Linux/macOS
cp .env.example .env
```

For a local Compose evaluation, the template's `POSTGRES_DB`, `POSTGRES_USER`,
and `POSTGRES_PASSWORD` values are the Compose defaults. Compose overrides
`DATABASE_URL` inside `app` so it connects to `db`, not `localhost`.

Set `MESH_API_KEY` before seeding the catalog or using AI recommendations. The
application can start without it, but the seed uses Mesh embeddings as part of
the PostgreSQL + Chroma `ProductService` dual-write. Replace the template
`SECRET_KEY` and `POSTGRES_PASSWORD` in every shared or non-development
environment. Keep `SCHEDULER_ENABLED=false` unless this instance is intended
to send scheduled digests.

### 3. Build, migrate, seed, and start

```bash
docker compose build
docker compose up -d db
docker compose run --rm app alembic upgrade head
docker compose run --rm app python scripts/seed_products.py
docker compose up -d
docker compose ps
```

The idempotent seed defines 30 professional e-learning courses. It creates
only missing courses through `ProductService`, synchronizing PostgreSQL,
Mesh embeddings, and Chroma.

### 4. Open SmartReco

Open [http://localhost:8000](http://localhost:8000), check
[health](http://localhost:8000/api/v1/health), or explore
[Swagger UI](http://localhost:8000/docs).

### 5. Stop or reset

```bash
docker compose down
```

`postgres_data` and `chroma_data` are named volumes, so this preserves the
database and vector store. Use `docker compose down -v` only to remove both
persisted stores and start fresh.

### Docker architecture

Compose runs `app` (FastAPI, Jinja2, and embedded Chroma) and `db`
(PostgreSQL 16). Mesh API remains external and is needed for embedding and
recommendation generation. LangSmith and SMTP are optional external services.

For a foreground startup, use `docker compose up --build` instead of `-d`.

### Environment configuration

Use `.env.example` as the complete template.

| Category | Variables | Purpose |
| --- | --- |
| Core Docker | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SECRET_KEY` | Database defaults and authentication signing. Compose sets its internal `DATABASE_URL` and Chroma directory. |
| AI | `MESH_API_KEY` | Required for catalog seeding and AI recommendations; blank is acceptable only when those paths are not used. |
| AI tuning | `MESH_EMBEDDING_MODEL`, `MESH_CHAT_MODEL`, `CHROMA_COLLECTION_NAME` | Optional model and collection configuration. |
| Optional observability | `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | Disabled by default. |
| Optional proactive delivery | `SCHEDULER_ENABLED`, `RECOMMENDATION_DIGEST_HOUR`, `RECOMMENDATION_DIGEST_MINUTE`, `RECOMMENDATION_DIGEST_TIMEZONE`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS`, `SMTP_TIMEOUT_SECONDS` | Scheduler and SMTP are disabled/unconfigured by default. |

`SUBMISSION_TOKEN` is not an application runtime setting. Store it only as a GitHub repository secret for the official challenge workflow. `MESH_API_KEY` is required both at runtime and as that workflow's GitHub secret.

## Local Python Setup

Option B — Local Python Setup is for developer/manual execution. Prerequisites:
Python 3.11, PostgreSQL, and a Mesh API key for catalog seeding or AI paths.

```bash
git clone <repository-url>
cd smartreco
python -m venv .venv
```

Activate the environment:

```powershell
# Windows
.venv\Scripts\Activate.ps1
```

```bash
# Linux/macOS
source .venv/bin/activate
```

Install dependencies and create local configuration:

```bash
pip install -r requirements.txt
# Windows PowerShell: Copy-Item .env.example .env
cp .env.example .env
```

Configure PostgreSQL in `.env`, then apply migrations and start the application:

```bash
alembic upgrade head
python -m uvicorn app.main:app --reload
```

## Demo Flow

### User

1. Log in as a regular user.
2. Browse, search, and open relevant products; spend time on a product.
3. SmartReco batches the behavioral events.
4. Open **Recommendations** when the trigger is eligible.
5. Review grounded products, reasons, and the generated narrative.

### Admin

1. Log in as an administrator and open **Admin**.
2. Create, edit, or delete a product.
3. ProductService keeps PostgreSQL and ChromaDB synchronized.

## Verification Evidence

| Check | Result |
| --- | --- |
| Full regression suite | 244 passed, 0 failed, 2 expected skips |
| Python compile gate | Passed |
| Real semantic retrieval E2E | Opt-in test available; not run in this audit (requires `RUN_REAL_MESH_E2E=true` and Mesh credentials) |
| Real recommendation E2E | Opt-in test available; not run in this audit (requires `RUN_REAL_MESH_E2E=true` and Mesh credentials) |
| SQL/Chroma dual-write | Passed — create, update, and delete |
| Professional catalog | 30 active courses seeded; PostgreSQL ↔ Chroma synchronization verified |
| Catalog seed idempotency | Verified — second run created 0 and skipped 30 |
| Docker Compose configuration | Passed — `app` and PostgreSQL `db`, health checks, port 8000, and named PostgreSQL/Chroma volumes resolve successfully |
| Official challenge checks | Workflow configuration verified locally; remote execution status was not available in this audit |

The workflow downloads and runs the organizer-supplied checker with GitHub
repository secrets; verify its remote result after pushing the final release.

## Repository Structure

```text
app/
  ai/            # behavior, retrieval, Mesh, and LangGraph components
  api/           # FastAPI endpoints
  services/      # application services
  repositories/  # PostgreSQL persistence
  templates/     # Jinja pages
  static/        # browser UI and event tracking
alembic/         # database migrations
tests/           # unit, API, and integration coverage
.github/workflows/ # official challenge checks
```

## Security and Production Thinking

- Passwords are hashed; browser authentication uses an HTTP-only JWT cookie.
- User/Admin authorization restricts product mutations to administrators.
- Secrets are environment-driven and `.env` is excluded from Git.
- Recommendations are catalog-grounded before persistence.
- Frontend tracking batches events; profile thresholds and cooldowns prevent unnecessary AI calls.

## Submission Status

SmartReco provides reproducible Docker Compose execution for local/evaluator
use; it is not a claim of production deployment. The automated challenge
coverage passes, including the opt-in real Mesh end-to-end tests. Tag the
commit selected for submission as the final release.
