# Edge-case register

Every discovered case is **Handled** with a named test, **Decided** with deliberate behavior, or
**Deferred** with a reason and extension point. Settings without end-to-end behavior are omitted.

## Policies and accruals

| Case | Status | Behavior / evidence |
|---|---|---|
| Policy settings change | Handled | A future-effective immutable version is appended; `test_future_policy_version_changes_only_future_accrual_periods`. |
| Arbitrary employee group | Handled | Assignment rows, not employment-type columns; `test_arbitrary_employee_lists_become_assignment_rows`. |
| Policies overlap in one category | Handled | Inclusive PostgreSQL exclusion constraint, including one-day ranges; `test_a_one_day_assignment_still_blocks_an_overlap`. |
| No policy for a category | Handled | Balance API returns `has_policy: false`; requests fail clearly; `test_seed_creates_one_coherent_idempotent_demo_story` and `test_a_category_without_a_policy_rejects_requests_clearly`. |
| Mid-period joiner | Handled | Admins choose prorated, full, or next-period accrual; `test_a_mid_period_joiner_is_prorated_by_eligible_calendar_days` and `test_new_hire_setting_supports_prorated_full_or_next_period_accrual`. |
| Scheduler replay or missed run | Handled | Deterministic keys make replay a no-op and later runs catch up; `test_a_missed_scheduler_run_catches_up_and_a_replay_is_a_no_op`. |
| Payroll replay | Handled | Payroll run ID is part of the source key; `test_payroll_replay_cannot_credit_the_same_work_twice`. |
| Accrual exceeds cap | Handled | Credit and forfeiture are separate entries; `test_balance_cap_keeps_credit_and_forfeiture_explainable`. |
| Six-hour employee | Handled | Day conversion reads Employee Service; `test_six_hour_employee_uses_a_six_hour_day_for_accrual_and_requests`. |
| Month-end and leap-day hire | Decided | Calendar-anchored periods tile regardless of hire day; `test_monthly_periods_tile_for_month_end_and_leap_day_hires`. |
| Tenure changes mid-period | Decided | New tier begins at the next period boundary; `test_tenure_tier_starts_on_the_first_future_period_boundary`. |
| Rollover replay | Handled | Expiry/carryover keys include employee, policy, year, and leg; `test_rollover_replay_is_a_no_op_and_expiry_is_separate_from_carryover`. |
| Snapshot differs from ledger | Decided | Ledger is authoritative; `test_snapshot_is_exactly_the_sum_of_the_ledger`. |

## Requests and access

| Case | Status | Behavior / evidence |
|---|---|---|
| Weekend or holiday range | Handled | Non-working dates create no frozen request-day row; `test_observed_holiday_is_stored_and_a_request_does_not_charge_it`. |
| No working dates | Handled | Rejected; `test_a_weekend_only_request_is_rejected`. |
| Partial time exceeds workday | Handled | Rejected using the employee's day length; `test_partial_time_is_single_day_and_cannot_exceed_a_workday`. |
| Partial time spans several days | Decided | Rejected rather than guessing allocation; `test_partial_time_is_single_day_and_cannot_exceed_a_workday`. |
| Negative balance | Handled | Disabled by default; an enabled policy enforces its explicit floor; `test_negative_balance_is_disabled_by_default_and_respects_an_explicit_floor`. |
| Overlapping live request | Handled | Pending and approved ranges block overlap; `test_pending_and_approved_requests_block_overlapping_dates`. |
| Two pending requests overspend | Handled | Holds reduce available balance; `test_two_pending_requests_cannot_spend_the_same_balance`. |
| Balance changes before approval | Handled | Locked snapshot is revalidated; `test_approval_revalidates_a_balance_that_changed_after_submission`. |
| Two admins approve concurrently | Handled | Request and snapshot rows are selected `FOR UPDATE`; debit source key is unique; `test_two_admins_approving_concurrently_create_one_debit`. |
| Denial | Handled | Hold released with no ledger entry; `test_denial_releases_the_hold_without_a_ledger_entry`. |
| Approved future request cancelled | Handled | Compensating reversal, never deletion; `test_cancelling_an_approved_request_appends_a_reversal`. |
| Leave already started | Decided | Employee cancellation is refused; `test_an_employee_cannot_cancel_leave_that_has_started`. |
| Holiday changes after submission | Decided | Frozen request-day costs remain; reconciliation is a future admin action; `test_holiday_changes_after_submission_do_not_reprice_frozen_request_days`. |
| Cross-year leave | Handled | Debit and reversal split by year; `test_cross_year_request_debits_and_reverses_each_policy_year`. |
| Employee guesses another URL | Handled | Server returns `403`; `test_an_employee_cannot_read_another_employees_requests`. |

## Deliberately deferred

| Case | Why | Extension point |
|---|---|---|
| Termination payout | State-specific wage/liability workflow | Publish final ledger balance to Payroll Service. |
| Payroll clawback after cancellation | Requires payroll reconciliation | Emit an outbox event from request reversal. |
| Rehire after service break | One start date cannot express service history | Employee Service employment periods. |
| Carryover credits with individual expiry | Requires FIFO allocation | Credit lots plus debit allocations. |
| Unpaid leave suspends accrual | Couples leave consumption to eligibility | Accrual eligibility adapter. |
| Blackout dates | Not required by the brief | Policy-scoped date ranges. |
