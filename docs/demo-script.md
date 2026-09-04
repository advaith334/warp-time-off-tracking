# Five-minute demo

Start from a clean database:

```bash
make up
make migrate
make seed
```

Run `make api` and `make web` separately, then open <http://localhost:5173>.

## 0:00–1:00 — employee view and working-day length

Act as **Ada Lovelace**. Her **My leave** view shows Vacation and **No policy set** for Maternity. Switch to
**Alan Turing**: the same 15-day grant is 5,400 minutes because his Employee Service schedule
defines a six-hour day. Employees see only **My leave** and **My requests**; admin routes also
enforce `403`, so hidden navigation is not the security boundary.

## 1:00–2:00 — frozen request and approval

Ada's **My requests** contains a pending two-day summer break created by the seed. Its 960 minutes
are held, so available time is below the ledger balance. Act as **Lindsey Poisson**, open
**Approvals**, and approve it. Expand **History** to show append-only transition events and actors.

## 2:00–3:00 — explain the number

Open **Audit**, select Ada, and walk the ordered ledger. The running total lands on the balance;
each accrual and debit retains its source identity and policy version. Job history also shows runs
that created zero entries—the visible proof of replay safety.

## 3:00–4:00 — time-dependent rules without database editing

Use the backend-only reviewer endpoints in <http://localhost:8000/docs> to move the date to
`2027-01-02` and run rollover twice. The first invocation posts expiration/carryover; the second
creates zero. Run accruals twice to demonstrate the same boundary. These controls stay out of the
admin product navigation.

## 4:00–5:00 — policy history and advanced rules

Open **Policies**. The form exposes caps, carryover/expiration, and a future tenure tier. Expand
**Version history** to show effective dates, reasons, and actors. Sync observed US holidays and note
that submitted requests retain their frozen cost if the calendar changes later.

Close with [the edge-case register](edge-cases.md): every known case is handled, deliberately
decided, or deferred with an extension point.
