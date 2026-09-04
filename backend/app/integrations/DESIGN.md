# External integration boundaries

The take-home uses deterministic in-process adapters so business behavior is runnable without credentials. Services depend on their small interfaces, not on copied external records.

## Boundary map

```mermaid
flowchart LR
    Services[Transaction services] --> Company[Company adapter]
    Services --> Employee[Employee adapter]
    Services --> Payroll[Payroll entry point]
    Services --> Holiday[Holiday source]
    Company -. production .-> CompanyAPI[Company service]
    Employee -. production .-> EmployeeAPI[Employee service]
    Payroll -. production .-> Queue[Payroll event queue]
    Holiday -. production .-> Calendar[Calendar provider]
```

| Adapter | Demo responsibility | Production replacement |
| --- | --- | --- |
| [`company_service.py`](company_service.py) | Stable company identity | Verified tenant claim or company API |
| [`employee_service.py`](employee_service.py) | Employees, managers, hire dates, workday lengths | Employee-directory client with cache and timeouts |
| [`payroll_service.py`](payroll_service.py) | Deterministic payroll event fixture | Queue/webhook consumer calling the same idempotent service |
| [`holiday_source.py`](holiday_source.py) | Observed US holiday dates | Company calendar provider or HR configuration |

## Ownership rules

| Data | Owner | Local persistence |
| --- | --- | --- |
| Company identity | Company service | Stable company ID references only |
| Employee profile and schedule | Employee service | Stable employee ID references only |
| Payroll run and worked minutes | Payroll system | Source IDs and resulting ledger entries |
| Company holidays | Time-off domain after sync | Company/date/name snapshot |
| Demo date | Local reviewer tooling | One `demo_state` row; never a production clock |

- Retries are expected: payroll and holiday entry points are idempotent or upsert-like.
- Authentication, transport retries, metrics, and circuit breaking belong in production adapters.
