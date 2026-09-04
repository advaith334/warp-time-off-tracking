export type Employee = {
  id: string
  name: string
  is_admin: boolean
}

export type Category = {
  id: string
  name: string
  icon: string | null
}

export type Rule = {
  method: 'TIME' | 'HOURS_WORKED'
  amount: string
  unit: 'DAY' | 'HOUR' | 'MINUTE'
  frequency: 'MONTHLY' | 'YEARLY' | null
  accrues_at: 'START_OF_PERIOD' | 'END_OF_PERIOD' | null
  min_tenure_months: number
}

export type PolicyVersion = {
  id: string
  version_no: number
  effective_from: string
  kind: 'UNLIMITED' | 'ACCRUAL'
  created_by: string
  change_reason: string
  max_balance_minutes: number | null
  carryover_cap_minutes: number | null
  expires_at_period_end: boolean
  tenure_transition: 'NEXT_PERIOD'
  rules: Rule[]
}

export type Policy = {
  id: string
  name: string
  category_id: string
  category_name: string
  created_by: string
  version_count: number
  current_version: PolicyVersion
}

export type Holiday = {
  id: string
  date: string
  name: string
  observed: boolean
}

export type Balance = {
  category_id: string
  category_name: string
  has_policy: boolean
  policy_id: string | null
  policy_name: string | null
  is_unlimited: boolean
  balance_minutes: number
  pending_hold_minutes: number
  available_minutes: number
  day_minutes: number
}

export type LedgerEntry = {
  id: string
  entry_type: string
  amount_minutes: number
  effective_date: string
  source_type: string
  source_id: string
  note: string | null
  created_at: string
}

export type JobRun = {
  id: string
  kind: 'SCHEDULED' | 'PAYROLL' | 'ROLLOVER'
  source_id: string
  status: string
  entries_created: number
  error: string | null
  created_at: string
}

export type TimeOffRequest = {
  id: string
  employee_id: string
  employee_name: string
  category_id: string
  reason: string
  status: 'PENDING' | 'APPROVED' | 'DENIED' | 'CANCELLED'
  start_date: string
  end_date: string
  total_minutes: number
  events: Array<{
    from_status: string | null
    to_status: string
    actor_id: string
    note: string | null
    at: string
  }>
}
