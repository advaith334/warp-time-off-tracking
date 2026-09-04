# Data model

This guide sits beside [`models.py`](models.py), the SQLAlchemy source of truth. Schema changes are explained in the [migration map](../migrations/README.md).

## Core relationships

```mermaid
erDiagram
    TIME_OFF_CATEGORIES ||--o{ POLICIES : classifies
    EMPLOYEE_GROUPS ||--o{ EMPLOYEE_GROUP_MEMBERS : contains
    EMPLOYEE_GROUPS ||--o{ POLICY_GROUP_TARGETS : selected_by
    POLICIES ||--o{ POLICY_GROUP_TARGETS : targets
    POLICIES ||--o{ POLICY_VERSIONS : versions
    POLICY_VERSIONS ||--o{ ACCRUAL_RULES : contains
    POLICIES ||--o{ POLICY_ASSIGNMENTS : assigned_by
    TIME_OFF_CATEGORIES ||--o{ POLICY_ASSIGNMENTS : scopes
    POLICIES ||--o{ LEDGER_ENTRIES : accounts_for
    POLICY_VERSIONS ||--o{ LEDGER_ENTRIES : explains
    TIME_OFF_REQUESTS ||--o{ REQUEST_DAYS : freezes
    TIME_OFF_REQUESTS ||--o{ REQUEST_EVENTS : records
    POLICIES ||--o{ TIME_OFF_REQUESTS : governs
    POLICIES ||--o{ BALANCE_SNAPSHOTS : caches
```

- Company and employee records remain in external adapters; local rows store their stable IDs.
- A request-to-ledger relationship is logical through source IDs, preserving append-only accounting.

## Table map

| Table | Purpose | Load-bearing invariant |
| --- | --- | --- |
| `time_off_categories` | Vacation, Sick, Maternity, and other company labels | Name is unique per company. |
| `employee_groups` | Reusable company-defined audiences | Name is unique per company. |
| `employee_group_members` | Company-managed employee classification | An employee belongs to at most one group per company. |
| `policies` | Stable identity for one category policy | Version history hangs from one identity. |
| `policy_group_targets` | Multi-select policy audience | A group targets a policy at most once. |
| `policy_versions` | Effective-dated configuration | Version number and effective date are unique per policy. |
| `accrual_rules` | Time or payroll rates, including tenure tiers | Every rule belongs to exactly one version. |
| `policy_assignments` | Effective-dated policy eligibility materialized from audiences | PostgreSQL excludes overlapping category ranges. |
| `ledger_entries` | Credits, debits, expiry, carryover, and reversal | Source type plus source ID is unique; services never update entries. |
| `balance_snapshots` | Rebuildable balance and pending-hold cache | Ledger wins if the snapshot ever disagrees. |
| `time_off_requests` | Frozen total and workflow status | Status changes only through request service transitions. |
| `request_days` | Charged minutes for each working date | Created once at submission; never repriced. |
| `request_events` | Actor, transition, time, and note | Append-only workflow history. |
| `holidays` | Company non-working dates | Company/date is unique, including observed dates. |
| `job_runs` | Scheduler, payroll, and rollover outcomes | Zero-entry replays remain visible. |
| `demo_state` | Deterministic reviewer clock | One keyed date; production uses the real clock adapter. |

## Accounting view

```mermaid
flowchart LR
    Sources[Accrual / payroll / request / rollover] --> Ledger[(ledger_entries)]
    Ledger --> Sum[SUM amount_minutes]
    Sum --> Balance[Authoritative balance]
    Ledger --> Snapshot[(balance_snapshots)]
    Snapshot --> FastRead[Fast balance + pending hold]
```

| Value | Stored as | Why |
| --- | --- | --- |
| Balance movement | Signed integer minutes | Exact across different employee workdays. |
| Policy history | Immutable version rows | Old ledger entries keep their original explanation. |
| Cancellation | Compensating ledger entry | Original debit remains auditable. |
| Request cost | Per-date frozen minutes | Calendar edits cannot silently alter submitted leave. |
