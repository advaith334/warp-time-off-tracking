# Employee Time Off Tracking

A compact, production-minded implementation of time-off policies, accruals, requests, approvals, and audit history. The repository favors a small understandable system: one React app, one FastAPI modular monolith, and one PostgreSQL database.

## Two-minute overview

Time is accounted for in integer minutes through an append-only ledger. Policies are effective-dated versions, requests freeze their calculated workdays, approvals run transactionally, and cancellations add compensating entries instead of rewriting history.

| Requirement | Where it lives |
| --- | --- |
| Employee and company boundaries | Deterministic adapters in [`backend/app/integrations`](backend/app/integrations) |
| Policy definitions and arbitrary assignments | Versioned policy and assignment services; [service flows](backend/app/services/DESIGN.md) |
| Scheduled and payroll accrual | Idempotent accrual entry points; [service flows](backend/app/services/DESIGN.md#accrual-flows) |
| Balances and auditability | Ledger-derived balances; [data model](backend/app/models.md) |
| Employee requests and admin approvals | Frozen days, holds, row locks, debit/reversal; [request flow](backend/app/services/DESIGN.md#request-flow) |
| Roles and company isolation | Server-side dependencies and scoped queries; [API boundary](backend/app/api/DESIGN.md) |
| Reviewer experience | Seeded story, demo clock, named edge cases, generated contracts, and CI |

## High-level design

```mermaid
flowchart LR
    Browser[React + Vite] --> API[FastAPI API]
    API --> Services[Transaction services]
    Services --> Domain[Pure domain rules]
    Services --> DB[(PostgreSQL)]
    Services --> Adapters[Employee / Company / Payroll / Holiday adapters]
```

- API routes validate identity and input; services own transactions; domain modules perform calculations.
- PostgreSQL constraints, row locks, and deterministic source keys protect accounting invariants.

## Documentation map

Detailed documentation is kept beside the code it describes.

| Topic | Co-located guide | Best starting question |
| --- | --- | --- |
| Database schema | [`backend/app/models.md`](backend/app/models.md) | Which records are authoritative, cached, or append-only? |
| Pure business rules | [`backend/app/domain/DESIGN.md`](backend/app/domain/DESIGN.md) | Which calculations are deterministic and side-effect free? |
| Business transactions | [`backend/app/services/DESIGN.md`](backend/app/services/DESIGN.md) | How do accrual, approval, and reversal work? |
| HTTP and authorization | [`backend/app/api/DESIGN.md`](backend/app/api/DESIGN.md) | Who can call each route family? |
| External boundaries | [`backend/app/integrations/DESIGN.md`](backend/app/integrations/DESIGN.md) | What is demo data, and what changes in production? |
| Migration history | [`backend/migrations/README.md`](backend/migrations/README.md) | Which behavior introduced each schema change? |
| Web application | [`frontend/src/DESIGN.md`](frontend/src/DESIGN.md) | What does each role see and how does data move? |
| Edge-case contract | [`docs/edge-cases.md`](docs/edge-cases.md) | What is handled, decided, or deferred? |
| Five-minute walkthrough | [`docs/demo-script.md`](docs/demo-script.md) | How can I review the product without editing data? |
| Generated API contract | [`docs/openapi.json`](docs/openapi.json) | What is the exact request/response surface? |

## Run locally

Requirements: Docker, Python 3.13+, Node.js 22+, and `make`.

```bash
make install
make up
make migrate
make seed
```

Start the API and web app in separate terminals:

```bash
make api
make web
```

Open [http://localhost:5173](http://localhost:5173). FastAPI runs at [http://localhost:8000](http://localhost:8000), and PostgreSQL uses port `5433`.

Run the same quality gate used by CI:

```bash
make check
```

It runs both test suites, backend and frontend lint, TypeScript checking, a production build, and OpenAPI/TypeScript contract generation. CI also rejects stale generated artifacts.

## Load-bearing decisions

| Decision | Consequence |
| --- | --- |
| Ledger instead of mutable balances | Every credit, debit, expiry, and reversal stays explainable. |
| Immutable policy versions | A new effective date cannot rewrite the reason for an old balance. |
| Frozen request days | Later calendar or policy changes do not silently reprice a request. |
| Minutes as the accounting unit | Six-hour and eight-hour workdays remain exact without floating-point days. |
| Injected external boundaries | Demo fixtures are deterministic; production integrations can replace adapters. |

## Scope and scaling

The synchronous modular monolith is deliberate. At higher volume, the same idempotent services can run behind a queue and outbox, while materialized projections accelerate reads without replacing the ledger as source of truth.

### Target production architecture

This is an evolutionary deployment design, not infrastructure currently shipped by this repository. The application remains a modular monolith while compute and background work scale independently.

```mermaid
flowchart TB
    Client[Web client] --> Edge[CloudFront + WAF]
    Edge --> Assets[(S3 static React assets)]
    Edge --> LB[Application Load Balancer]

    subgraph ECS[Autoscaled ECS / Fargate services]
        API[Stateless FastAPI tasks]
        Relay[Transactional outbox relay]
        Workers[Accrual + integration workers]
    end

    LB --> API
    API --> Proxy[RDS Proxy]
    Workers --> Proxy
    Relay -- polls outbox --> Proxy
    Proxy --> Primary[(RDS PostgreSQL Multi-AZ)]
    Primary -. asynchronous replication .-> Replica[(Read replica)]
    API -. reporting reads .-> Replica

    Scheduler[EventBridge Scheduler] --> Queue[SQS + dead-letter queue]
    Relay --> Queue
    Queue --> Workers

    API --> External[Employee / Company / Payroll / Holiday services]
    Workers --> External
    API --> Telemetry[Logs / metrics / traces]
    Workers --> Telemetry
    Secrets[Secrets Manager] --> API
    Secrets --> Workers
```

| Layer | Scaling and reliability role |
| --- | --- |
| CDN, WAF, and load balancer | Cache static assets, protect the edge, and spread API traffic across healthy tasks. |
| Stateless FastAPI tasks | Scale horizontally without session affinity; authorization remains company-scoped. |
| RDS Proxy and Multi-AZ PostgreSQL | Pool bursty connections and preserve transactional ledger guarantees through failover. |
| Transactional outbox, SQS, and workers | Move scheduled accrual and integration work off request paths without losing committed jobs. |
| Read replica and projections | Isolate reporting traffic while PostgreSQL remains the accounting source of truth. |
| Dead-letter queue and telemetry | Surface exhausted retries and connect each request, job, and ledger mutation for diagnosis. |

- Partition background work by company or employee and retain the existing idempotency keys for safe retries.
- Add replicas, projections, and workers in response to measured load rather than splitting domain transactions prematurely.

Production SSO, live payroll webhooks, notifications, distributed scheduling, and partial time spread over several dates are intentionally deferred. Reasons and extension points are recorded in the [edge-case contract](docs/edge-cases.md).

## Fifteen-minute review path

1. Read this page and the [data model](backend/app/models.md).
2. Follow the [policy, accrual, and request flows](backend/app/services/DESIGN.md).
3. Check the [API access matrix](backend/app/api/DESIGN.md) and [frontend role map](frontend/src/DESIGN.md).
4. Trace named tests from the [edge-case contract](docs/edge-cases.md).
5. Run the [five-minute demo](docs/demo-script.md) and `make check`.
