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
}

export type Policy = {
  id: string
  name: string
  category_id: string
  category_name: string
  created_by: string
  version_count: number
  current_version: {
    version_no: number
    effective_from: string
    kind: 'UNLIMITED' | 'ACCRUAL'
    rules: Rule[]
  }
}

export type Balance = {
  category_id: string
  category_name: string
  has_policy: boolean
  policy_id: string | null
  policy_name: string | null
  is_unlimited: boolean
  balance_minutes: number
  day_minutes: number
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
}
