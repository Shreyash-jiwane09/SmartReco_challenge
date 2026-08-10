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

### Bonus feature status

- **LangGraph — VERIFIED.** The explicit recommendation workflow runs
  `prepare_context` → `generate_recommendation` → `validate_grounding`.
- **Retrieval polish — VERIFIED.** Chroma retrieval filters to active-product
  metadata, then PostgreSQL re-grounds candidates and rejects invalid, stale,
  or inactive products. This is not reranking, hybrid search, or graph
  retrieval.
- **LangSmith — IMPLEMENTED AND VERIFIED.** Optional tracing records
  recommendation workflow visibility in the `smartreco-build-challenge-2026`
  trace project; normal operation remains silent when tracing is disabled.
- **Scheduled proactive delivery — IMPLEMENTED BUT NOT RUNTIME VERIFIED.**
  APScheduler runs the existing recommendation service for eligible users and
  sends SMTP digests from persisted, catalog-grounded recommendations.
  Implementation and tests are complete; final scheduler-to-email runtime
  proof should be captured before claiming end-to-end scheduled delivery
  verification.

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
- GitHub Actions

## Setup

Prerequisites: Python 3.11, PostgreSQL, and a Mesh API key.

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
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS
```

Configure PostgreSQL in `.env`, then apply migrations and start the application:

```bash
alembic upgrade head
python -m uvicorn app.main:app --reload
```

The application serves API documentation at `/docs` by default.

## Docker Quick Start

This runs SmartReco and PostgreSQL in containers while keeping the embedded
Chroma store in a named Docker volume. Mesh, LangSmith, and SMTP remain
external and optional. Docker does not run migrations or seed the catalog
automatically, keeping those release operations explicit and repeatable.

```bash
cp .env.example .env  # Windows PowerShell: Copy-Item .env.example .env
```

Set `MESH_API_KEY` in `.env` before catalog seeding. The supplied
`POSTGRES_*` values are local-development defaults; replace `POSTGRES_PASSWORD`
and `SECRET_KEY` for any shared environment. Leave `SCHEDULER_ENABLED=false`
unless this is the one process intended to send scheduled digests.

```bash
docker compose up --build -d
docker compose run --rm app alembic upgrade head
docker compose run --rm app python scripts/seed_products.py
```

Open [http://localhost:8000](http://localhost:8000) (API health:
[http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)).
The catalog seed uses `ProductService`, so it needs valid Mesh credentials to
write both PostgreSQL and Chroma. Stop the stack with `docker compose down`;
do not add `-v` if you want to preserve the database and vector store.

For a foreground startup, use `docker compose up --build` instead of `-d`.

### Environment configuration

Use `.env.example` as the complete template. Key runtime settings are:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL |
| `MESH_API_KEY` | Mesh embeddings and chat access |
| `MESH_EMBEDDING_MODEL`, `MESH_CHAT_MODEL` | Mesh model selection |
| `CHROMA_COLLECTION_NAME`, `CHROMA_PERSIST_DIRECTORY` | Vector-store configuration |
| `SECRET_KEY`, `JWT_ALGORITHM` | Authentication token configuration |
| `CORS_ORIGINS` | Allowed browser origins |

`SUBMISSION_TOKEN` is not an application runtime setting. Store it only as a GitHub repository secret for the official challenge workflow. `MESH_API_KEY` is required both at runtime and as that workflow's GitHub secret.

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
| Real semantic retrieval E2E | Passed — Mesh embeddings, isolated ChromaDB, and PostgreSQL grounding of four catalog products |
| Real recommendation E2E | Passed — persisted behavior through LangGraph, Mesh Chat, grounding, and PostgreSQL recommendation read-back |
| SQL/Chroma dual-write | Passed — create, update, and delete |
| Professional catalog | 30 active courses seeded; PostgreSQL ↔ Chroma synchronization verified |
| Catalog seed idempotency | Verified — second run created 0 and skipped 30 |
| Official challenge checks | 4/4 critical checks passed |

The organizer workflow could not record its result only because the final hackathon project entry had not yet been created; this is not a CI failure.

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

The technical challenge checks and real end-to-end verification pass. Final submission preparation is in progress.
