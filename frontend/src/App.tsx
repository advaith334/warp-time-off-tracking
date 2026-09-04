import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, api, setActor } from './api/client'
import type {
  Balance,
  Category,
  Employee,
  EmployeeGroup,
  Holiday,
  JobRun,
  LedgerEntry,
  Policy,
  PolicyVersion,
  RequestPreview,
  TimeOffRequest,
} from './api/types'

const inputClass = 'field-control'
const buttonClass = 'button button-primary'
const secondaryButtonClass = 'button button-secondary'
type Tab = 'overview' | 'calendar' | 'requests' | 'policies' | 'people' | 'audit'

const tabDescriptions: Record<Tab, string> = {
  overview: 'Balances and policy coverage at a glance',
  calendar: 'Holidays and team leave across the year',
  requests: 'Submit, review, and track time-off requests',
  policies: 'Define how each leave type is earned, assigned, and carried over',
  people: 'Reference group eligibility; Employee Service owns membership in production',
  audit: 'Follow every balance change back to its source',
}

const monthNames = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]
const weekdayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function monthId(value: string) {
  return 'month-' + value.slice(0, 7)
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
  }).format(new Date(value + 'T00:00:00Z'))
}

function formatMinutes(minutes: number, dayMinutes = 480) {
  if (minutes === 0) return '0 hours'
  const sign = minutes < 0 ? '−' : ''
  const absolute = Math.abs(minutes)
  const days = Math.floor(absolute / dayMinutes)
  const remaining = absolute % dayMinutes
  const hours = Math.floor(remaining / 60)
  const leftoverMinutes = remaining % 60
  const parts = [
    days ? `${days} ${days === 1 ? 'day' : 'days'}` : '',
    hours ? `${hours} ${hours === 1 ? 'hour' : 'hours'}` : '',
    leftoverMinutes ? `${leftoverMinutes} min` : '',
  ].filter(Boolean)
  return sign + parts.join(' ')
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="field-label"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${status.toLowerCase()}`}><span />{status.toLowerCase()}</span>
}

function policySummary(policy: Policy) {
  if (policy.current_version.kind === 'UNLIMITED') return 'Unlimited time off'
  const rule = policy.current_version.rules[0]
  if (!rule) return 'No accrual rule'
  const amount = Number(rule.amount).toLocaleString('en-US', { maximumFractionDigits: 2 })
  if (rule.method === 'HOURS_WORKED') {
    return `${amount} ${rule.unit.toLowerCase()} per ${(rule.per_minutes_worked ?? 0) / 60} hours worked`
  }
  const cadence = {
    DAILY: 'day', WEEKLY: 'week', SEMIMONTHLY: 'half-month',
    BIWEEKLY: 'two weeks', MONTHLY: 'month', YEARLY: 'year',
  }[rule.frequency ?? 'YEARLY']
  return `${amount} ${rule.unit.toLowerCase()}${Number(rule.amount) === 1 ? '' : 's'} per ${cadence}`
}

function employeePolicySummary(policy: Policy, dayMinutes: number) {
  const audience = policy.all_employees
    ? 'Applies to everyone in the company'
    : `Applies to: ${policy.group_names.join(', ')}`
  if (policy.current_version.kind === 'UNLIMITED') {
    return {
      headline: 'No fixed limit',
      details: [audience, 'Requests still go through approval'],
    }
  }
  const rule = [...policy.current_version.rules]
    .sort((left, right) => left.min_tenure_months - right.min_tenure_months)[0]
  if (!rule) return { headline: 'Earning rules are not configured', details: [] }
  const amount = Number(rule.amount).toLocaleString('en-US', { maximumFractionDigits: 2 })
  const unit = `${rule.unit.toLowerCase()}${Number(rule.amount) === 1 ? '' : 's'}`
  const cadence = {
    DAILY: 'day', WEEKLY: 'week', SEMIMONTHLY: 'half-month',
    BIWEEKLY: 'two weeks', MONTHLY: 'month', YEARLY: 'year',
  }[rule.frequency ?? 'YEARLY']
  const headline = rule.method === 'HOURS_WORKED'
    ? `${amount} ${unit} earned every ${(rule.per_minutes_worked ?? 0) / 60} hours worked`
    : `${amount} ${unit} added each ${cadence}`
  const details = [
    audience,
    policy.current_version.max_balance_minutes
      ? `Balance capped at ${formatMinutes(policy.current_version.max_balance_minutes, dayMinutes)}`
      : '',
    policy.current_version.carryover_cap_minutes
      ? `Up to ${formatMinutes(policy.current_version.carryover_cap_minutes, dayMinutes)} carries over`
      : '',
    policy.current_version.expires_at_period_end ? 'Unused time expires at year-end' : '',
    policy.current_version.allow_negative
      ? `Can go down to ${formatMinutes(policy.current_version.negative_floor_minutes, dayMinutes)}`
      : 'Balance cannot go below zero',
  ].filter(Boolean)
  return { headline, details }
}

function dayAfter(value: string) {
  const result = new Date(value + 'T00:00:00Z')
  result.setUTCDate(result.getUTCDate() + 1)
  return result.toISOString().slice(0, 10)
}

export default function App() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [policies, setPolicies] = useState<Policy[]>([])
  const [groups, setGroups] = useState<EmployeeGroup[]>([])
  const [balances, setBalances] = useState<Balance[]>([])
  const [requests, setRequests] = useState<TimeOffRequest[]>([])
  const [holidays, setHolidays] = useState<Holiday[]>([])
  const [jobRuns, setJobRuns] = useState<JobRun[]>([])
  const [ledger, setLedger] = useState<LedgerEntry[]>([])
  const [versions, setVersions] = useState<Record<string, PolicyVersion[]>>({})
  const [actorId, setActorId] = useState('adm_lindsey')
  const [auditEmployeeId, setAuditEmployeeId] = useState('emp_ada')
  const [tab, setTab] = useState<Tab>('overview')
  const [today, setToday] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [showAdvancedPolicy, setShowAdvancedPolicy] = useState(false)
  const [categoryName, setCategoryName] = useState('')
  const [policyName, setPolicyName] = useState('')
  const [allEmployees, setAllEmployees] = useState(true)
  const [policyGroupIds, setPolicyGroupIds] = useState<string[]>([])
  const [groupName, setGroupName] = useState('')
  const [editingPolicyId, setEditingPolicyId] = useState<string | null>(null)
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [changeReason, setChangeReason] = useState('Policy created')
  const [kind, setKind] = useState<'ACCRUAL' | 'UNLIMITED'>('ACCRUAL')
  const [accrualMethod, setAccrualMethod] = useState<'TIME' | 'HOURS_WORKED'>('TIME')
  const [amount, setAmount] = useState('20')
  const [frequency, setFrequency] = useState<'DAILY' | 'WEEKLY' | 'SEMIMONTHLY' | 'BIWEEKLY' | 'MONTHLY' | 'YEARLY'>('YEARLY')
  const [perHoursWorked, setPerHoursWorked] = useState('30')
  const [newHireProration, setNewHireProration] = useState<'PRORATE' | 'FULL' | 'NONE'>('PRORATE')
  const [allowNegative, setAllowNegative] = useState(false)
  const [negativeFloor, setNegativeFloor] = useState('-8')
  const [tenureMonths, setTenureMonths] = useState('')
  const [tenureAmount, setTenureAmount] = useState('')
  const [maxBalance, setMaxBalance] = useState('')
  const [carryoverCap, setCarryoverCap] = useState('')
  const [expires, setExpires] = useState(false)
  const [categoryId, setCategoryId] = useState('')
  const [requestCategoryId, setRequestCategoryId] = useState('')
  const [requestStart, setRequestStart] = useState('')
  const [requestEnd, setRequestEnd] = useState('')
  const [requestReason, setRequestReason] = useState('')
  const [customRequestType, setCustomRequestType] = useState('')
  const [isPartialDay, setIsPartialDay] = useState(false)
  const [requestHours, setRequestHours] = useState('')
  const [requestMinutes, setRequestMinutes] = useState('')
  const [requestPreview, setRequestPreview] = useState<RequestPreview | null>(null)

  const actor = employees.find((employee) => employee.id === actorId)
  const teamMembers = employees.filter((employee) => !employee.is_admin)
  const selectedAuditEmployee = employees.find((employee) => employee.id === auditEmployeeId)
  const isOtherRequest = categories.find((category) => category.id === requestCategoryId)?.name === 'Other'
  const pendingRequests = requests.filter((request) => request.status === 'PENDING')
  const tabs: Array<{ id: Tab; label: string; qualifier?: string }> = actor?.is_admin
    ? [
        { id: 'overview', label: 'All' },
        { id: 'calendar', label: 'Calendar' },
        { id: 'policies', label: 'Policies' },
        { id: 'people', label: 'Groups', qualifier: 'Employee Service' },
        { id: 'requests', label: 'Approvals' },
        { id: 'audit', label: 'Audit' },
      ]
    : [
        { id: 'overview', label: 'My leave' },
        { id: 'requests', label: 'My requests' },
      ]

  async function load() {
    try {
      const [people, cats, policyRows, groupRows, state] = await Promise.all([
        api.get<Employee[]>('/employees'),
        api.get<Category[]>('/categories'),
        api.get<Policy[]>('/policies'),
        api.get<EmployeeGroup[]>('/groups'),
        api.get<{ today: string }>('/dev/state'),
      ])
      const holidayRows = await api.get<Holiday[]>('/holidays?year=' + state.today.slice(0, 4))
      setEmployees(people)
      setCategories(cats)
      setPolicies(policyRows)
      setGroups(groupRows)
      setHolidays(holidayRows)
      setToday(state.today)
      setEffectiveFrom((current) => current || state.today)
      setAuditEmployeeId((current) => current || people.find((person) => !person.is_admin)?.id || '')
      setCategoryId((current) => current || cats[0]?.id || '')
      setRequestCategoryId((current) => current || cats[0]?.id || '')
      setError('')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    } finally {
      setLoading(false)
    }
  }

  // Initial API hydration is the external synchronization this effect owns.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { void load() }, [])

  useEffect(() => {
    if (!today) return
    api.get<Balance[]>('/employees/' + actorId + '/balances?on_date=' + today)
      .then(setBalances)
      .catch(() => setBalances([]))
  }, [actorId, today])

  useEffect(() => {
    api.get<TimeOffRequest[]>('/requests').then(setRequests).catch(() => setRequests([]))
  }, [actorId])

  useEffect(() => {
    if (!actor?.is_admin || tab !== 'audit' || !auditEmployeeId || !today) return
    Promise.all([
      api.get<LedgerEntry[]>('/employees/' + auditEmployeeId + '/ledger'),
      api.get<JobRun[]>('/audit/job-runs'),
    ]).then(([entries, runs]) => {
      setLedger(entries)
      setJobRuns(runs)
    }).catch((caught) => setError(String(caught)))
  }, [actor?.is_admin, auditEmployeeId, tab, today])

  async function perform(action: string, successMessage: string, work: () => Promise<void>) {
    setBusyAction(action)
    setError('')
    setSuccess('')
    try {
      await work()
      setSuccess(successMessage)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    } finally {
      setBusyAction('')
    }
  }

  async function createCategory(event: React.FormEvent) {
    event.preventDefault()
    await perform('category', 'Category created.', async () => {
      await api.post('/categories', { name: categoryName })
      setCategoryName('')
      setShowCategoryForm(false)
      await load()
    })
  }

  async function savePolicy(event: React.FormEvent) {
    event.preventDefault()
    const rule = (ruleAmount: string, minTenureMonths: number) => accrualMethod === 'TIME'
      ? {
          method: 'TIME', amount: ruleAmount, unit: 'DAY', frequency,
          accrues_at: 'START_OF_PERIOD', per_minutes_worked: null,
          min_tenure_months: minTenureMonths,
        }
      : {
          method: 'HOURS_WORKED', amount: ruleAmount, unit: 'HOUR',
          frequency: null, accrues_at: null,
          per_minutes_worked: Number(perHoursWorked) * 60,
          min_tenure_months: minTenureMonths,
        }
    const rules = kind === 'UNLIMITED' ? [] : [
      rule(amount, 0),
      ...(tenureMonths && tenureAmount
        ? [rule(tenureAmount, Number(tenureMonths))]
        : []),
    ]
    const policyFields = {
      name: policyName, effective_from: effectiveFrom, kind, rules,
      all_employees: allEmployees,
      group_ids: allEmployees ? [] : policyGroupIds,
      change_reason: changeReason,
      new_hire_proration: newHireProration,
      allow_negative: allowNegative,
      negative_floor_minutes: allowNegative ? Number(negativeFloor) * 60 : 0,
      max_balance_minutes: maxBalance ? Number(maxBalance) * 60 : null,
      carryover_cap_minutes: carryoverCap ? Number(carryoverCap) * 60 : null,
      expires_at_period_end: expires, tenure_transition: 'NEXT_PERIOD',
    }
    await perform('policy', editingPolicyId ? 'New policy version scheduled.' : 'Policy created.', async () => {
      if (editingPolicyId) {
        await api.put('/policies/' + editingPolicyId, policyFields)
      } else {
        await api.post<Policy>('/policies', {
          ...policyFields, category_id: categoryId,
        })
      }
      setPolicyName('')
      setAllEmployees(true)
      setPolicyGroupIds([])
      setEditingPolicyId(null)
      setChangeReason('Policy created')
      setShowAdvancedPolicy(false)
      setVersions({})
      await load()
    })
  }

  function beginPolicyUpdate(policy: Policy) {
    const rules = [...policy.current_version.rules]
      .sort((left, right) => left.min_tenure_months - right.min_tenure_months)
    const [base, tier] = rules
    setEditingPolicyId(policy.id)
    setPolicyName(policy.name)
    setAllEmployees(policy.all_employees)
    setPolicyGroupIds(policy.group_ids)
    setCategoryId(policy.category_id)
    setEffectiveFrom(today > policy.current_version.effective_from
      ? today
      : dayAfter(policy.current_version.effective_from))
    setChangeReason('')
    setKind(policy.current_version.kind)
    setAccrualMethod(base?.method ?? 'TIME')
    setAmount(base ? String(Number(base.amount)) : '20')
    setFrequency(base?.frequency ?? 'YEARLY')
    setPerHoursWorked(base?.per_minutes_worked
      ? String(base.per_minutes_worked / 60)
      : '30')
    setNewHireProration(policy.current_version.new_hire_proration)
    setAllowNegative(policy.current_version.allow_negative)
    setNegativeFloor(String((policy.current_version.negative_floor_minutes || -480) / 60))
    setMaxBalance(policy.current_version.max_balance_minutes
      ? String(policy.current_version.max_balance_minutes / 60)
      : '')
    setCarryoverCap(policy.current_version.carryover_cap_minutes
      ? String(policy.current_version.carryover_cap_minutes / 60)
      : '')
    setExpires(policy.current_version.expires_at_period_end)
    setTenureMonths(tier?.min_tenure_months.toString() ?? '')
    setTenureAmount(tier ? String(Number(tier.amount)) : '')
  }

  function cancelPolicyUpdate() {
    setEditingPolicyId(null)
    setPolicyName('')
    setAllEmployees(true)
    setPolicyGroupIds([])
    setChangeReason('Policy created')
    setEffectiveFrom(today)
  }

  async function syncHolidays() {
    await perform('holidays', 'Holiday calendar synchronized.', async () => {
      setHolidays(await api.post<Holiday[]>('/holidays/sync?year=' + today.slice(0, 4)))
    })
  }

  function toggleId(values: string[], id: string) {
    return values.includes(id) ? values.filter((value) => value !== id) : [...values, id]
  }

  async function createGroup(event: React.FormEvent) {
    event.preventDefault()
    await perform('group-create', 'Employee group created.', async () => {
      await api.post('/groups', { name: groupName, employee_ids: [] })
      setGroupName('')
      await load()
    })
  }

  async function assignEmployeeGroup(employeeId: string, groupId: string) {
    await perform('membership-' + employeeId, 'Employee group updated.', async () => {
      await api.put('/employees/' + employeeId + '/group', {
        group_id: groupId || null, effective_from: today,
      })
      await load()
    })
  }

  async function removeGroup(groupId: string) {
    await perform('group-' + groupId, 'Employee group removed.', async () => {
      await api.delete('/groups/' + groupId)
      await load()
    })
  }

  async function loadVersions(policyId: string) {
    if (versions[policyId]) return
    const rows = await api.get<PolicyVersion[]>('/policies/' + policyId + '/versions')
    setVersions((current) => ({ ...current, [policyId]: rows }))
  }

  function requestPayload() {
    const reason = isOtherRequest
      ? `${customRequestType}${requestReason ? ` — ${requestReason}` : ''}`
      : requestReason || 'Time off'
    return {
      employee_id: actorId, category_id: requestCategoryId, reason,
      start_date: requestStart, end_date: requestEnd,
      hours: !isPartialDay || requestHours === '' ? null : Number(requestHours),
      minutes: !isPartialDay || requestMinutes === '' ? null : Number(requestMinutes),
    }
  }

  async function refreshSelfService() {
    const [requestRows, balanceRows] = await Promise.all([
      api.get<TimeOffRequest[]>('/requests'),
      api.get<Balance[]>('/employees/' + actorId + '/balances?on_date=' + today),
    ])
    setRequests(requestRows)
    setBalances(balanceRows)
  }

  async function previewRequest() {
    setBusyAction('preview')
    try {
      setRequestPreview(await api.post<RequestPreview>('/requests/preview', requestPayload()))
      setError('')
    } catch (caught) {
      setRequestPreview(null)
      setError(caught instanceof ApiError ? caught.message : String(caught))
    } finally {
      setBusyAction('')
    }
  }

  async function submitRequest(event: React.FormEvent) {
    event.preventDefault()
    await perform('request', 'Request submitted for approval.', async () => {
      await api.post('/requests', requestPayload())
      setRequestPreview(null)
      setRequestReason('')
      setCustomRequestType('')
      setRequestStart('')
      setRequestEnd('')
      setRequestHours('')
      setRequestMinutes('')
      setIsPartialDay(false)
      await refreshSelfService()
    })
  }

  async function cancelRequest(requestId: string) {
    await perform('cancel-' + requestId, 'Request cancelled and balance restored.', async () => {
      await api.post('/requests/' + requestId + '/cancel')
      await refreshSelfService()
    })
  }

  async function decide(requestId: string, action: 'approve' | 'deny') {
    await perform(action + '-' + requestId, `Request ${action === 'approve' ? 'approved' : 'denied'}.`, async () => {
      await api.post('/requests/' + requestId + '/' + action, {})
      setRequests(await api.get<TimeOffRequest[]>('/requests'))
    })
  }

  const runningLedger = useMemo(() => {
    return ledger.map((entry, index) => ({
      ...entry,
      running: ledger
        .slice(0, index + 1)
        .reduce((total, row) => total + row.amount_minutes, 0),
    }))
  }, [ledger])

  const calendarYear = Number(today.slice(0, 4)) || new Date().getFullYear()
  const calendarEvents = useMemo(() => {
    const byDate = new Map<string, Array<{
      id: string
      label: string
      kind: 'holiday' | 'leave'
      status?: string
    }>>()
    const add = (date: string, event: {
      id: string
      label: string
      kind: 'holiday' | 'leave'
      status?: string
    }) => byDate.set(date, [...(byDate.get(date) ?? []), event])
    holidays.forEach((holiday) => add(holiday.date, {
      id: holiday.id, label: holiday.name, kind: 'holiday',
    }))
    requests
      .filter((request) => request.status === 'PENDING' || request.status === 'APPROVED')
      .forEach((request) => request.days.forEach((day) => add(day.date, {
        id: request.id,
        label: `${request.employee_name.split(' ')[0]} · ${request.status.toLowerCase()}`,
        kind: 'leave',
        status: request.status,
      })))
    return byDate
  }, [holidays, requests])

  function showCalendarDate(date: string) {
    const month = document.getElementById(monthId(date))
    month?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    month?.focus({ preventScroll: true })
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true"><span /></div>
            <div>
              <p className="eyebrow">Northstar / People ops</p>
              <h1>Time away</h1>
            </div>
          </div>
          <div className="identity-switcher">
            <div className="avatar" aria-hidden="true">{actor?.name?.split(' ').map((part) => part[0]).join('').slice(0, 2) || '—'}</div>
            <label>
              <span>Viewing as {actor?.is_admin ? 'administrator' : 'employee'}</span>
              <select aria-label="Acting as" value={actorId} onChange={(event) => {
                setActorId(event.target.value)
                setActor(event.target.value)
                setTab('overview')
                setError('')
                setSuccess('')
              }}>
                {employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}
              </select>
            </label>
          </div>
        </div>
        <div className="nav-wrap">
          <nav aria-label="Product sections">
            {tabs.map((item) => <button key={item.id} type="button" aria-label={item.qualifier ? `${item.label} (${item.qualifier})` : item.label} aria-current={tab === item.id ? 'page' : undefined} onClick={() => {
              setTab(item.id)
              setError('')
              setSuccess('')
            }}><span className="nav-label">{item.label}{item.qualifier && <small>({item.qualifier})</small>}</span>{item.id === 'requests' && actor?.is_admin && pendingRequests.length > 0 && <span className="nav-count" aria-hidden="true">{pendingRequests.length}</span>}</button>)}
          </nav>
        </div>
      </header>

      <main className="page-content">
        <div className="page-heading">
          <div>
            <p className="eyebrow">{actor?.is_admin ? 'Admin workspace' : 'Employee workspace'}</p>
            <h2>{tabs.find((item) => item.id === tab)?.label}</h2>
            <p>{tab === 'overview' && !actor?.is_admin ? 'See what leave is available and plan your next request' : tabDescriptions[tab]}</p>
          </div>
          {tab === 'overview' && !actor?.is_admin && <button className={buttonClass} type="button" onClick={() => setTab('requests')}>Request time off <span aria-hidden="true">→</span></button>}
          {tab === 'policies' && actor?.is_admin && <button className={secondaryButtonClass} type="button" onClick={() => setShowCategoryForm((value) => !value)}>{showCategoryForm ? 'Close category form' : '+ New category'}</button>}
        </div>

        {loading && <div className="loading-card"><span className="spinner" />Loading your workspace…</div>}
        {error && <div className="notice notice-error" role="alert"><div><strong>Something needs attention</strong><p>{error}</p></div><button type="button" aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}
        {success && <div className="notice notice-success" role="status"><div><strong>All set</strong><p>{success}</p></div><button type="button" aria-label="Dismiss message" onClick={() => setSuccess('')}>×</button></div>}

        {!loading && tab === 'overview' && actor?.is_admin && (
          <section className="dashboard-grid">
            <article className="stat-card accent-violet"><span>Pending approvals</span><strong>{pendingRequests.length}</strong><p>{pendingRequests.length === 1 ? 'request needs' : 'requests need'} a decision</p><button type="button" onClick={() => setTab('requests')}>Review queue →</button></article>
            <article className="stat-card accent-teal"><span>Active policies</span><strong>{policies.length}</strong><p>Across {categories.length} time-off {categories.length === 1 ? 'category' : 'categories'}</p><button type="button" onClick={() => setTab('policies')}>Manage policies →</button></article>
            <article className="stat-card accent-amber"><span>Holiday calendar</span><strong>{holidays.length}</strong><p>Observed holidays loaded for {today.slice(0, 4)}</p><button type="button" onClick={() => setTab('calendar')}>Review calendar →</button></article>
            <article className="content-card dashboard-wide">
              <div className="card-heading"><div><p className="eyebrow">Team snapshot</p><h3>Policy coverage</h3></div><span className="soft-chip">{employees.filter((employee) => !employee.is_admin).length} employees</span></div>
              <div className="coverage-list">{policies.map((policy) => <div key={policy.id}><span className="category-icon">{policy.category_name.slice(0, 1)}</span><div><strong>{policy.name}</strong><p>{policySummary(policy)}</p></div><span className="version-chip">v{policy.current_version.version_no}</span></div>)}</div>
            </article>
          </section>
        )}

        {!loading && tab === 'overview' && !actor?.is_admin && (
          <section className="balance-grid">
            {balances.map((balance, index) => {
              const leavePolicy = policies.find((policy) => policy.id === balance.policy_id)
              const explanation = leavePolicy
                ? employeePolicySummary(leavePolicy, balance.day_minutes)
                : null
              return <article key={balance.category_id} className={`balance-card balance-${index % 3}`}>
                <div className="balance-top"><span className="category-icon">{balance.category_name.slice(0, 1)}</span><span className="soft-chip">{balance.has_policy ? 'Available to you' : 'Not available'}</span></div>
                <p>{balance.category_name}</p>
                <strong>{!balance.has_policy ? 'Not offered' : balance.is_unlimited ? 'No fixed limit' : formatMinutes(balance.available_minutes, balance.day_minutes)}</strong>
                <span>{!balance.has_policy ? 'This leave type is not offered for your role' : balance.is_unlimited ? 'Requests still require approval' : 'available to request'}</span>
                {balance.pending_hold_minutes > 0 && <div className="pending-note"><span />{formatMinutes(balance.pending_hold_minutes, balance.day_minutes)} awaiting approval</div>}
                {explanation && <details className="leave-explanation"><summary>How this leave works</summary><strong>{explanation.headline}</strong>{explanation.details.map((detail) => <span key={detail}>• {detail}</span>)}</details>}
              </article>
            })}
            {balances.length === 0 && <div className="empty-state"><div>◌</div><h3>No time-off categories yet</h3><p>Your administrator has not configured any categories.</p></div>}
          </section>
        )}

        {actor?.is_admin && tab === 'calendar' && <section className="calendar-layout">
          <aside className="calendar-index">
            <div><p className="eyebrow">Year index</p><h3>{calendarYear} calendar</h3><p>Jump directly to any holiday or leave request.</p></div>
            <div className="calendar-legend"><span><i className="legend-holiday" />Holiday</span><span><i className="legend-approved" />Approved</span><span><i className="legend-pending" />Pending</span></div>
            <section><h4>Company holidays <span>{holidays.length}</span></h4><div className="index-list">{[...holidays].sort((left, right) => left.date.localeCompare(right.date)).map((holiday) => <button type="button" key={holiday.id} onClick={() => showCalendarDate(holiday.date)}><time>{new Date(holiday.date + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })}</time><span>{holiday.name}</span><b>→</b></button>)}</div></section>
            <section><h4>Team leave <span>{requests.filter((request) => request.status === 'PENDING' || request.status === 'APPROVED').length}</span></h4><div className="index-list leave-index">{requests.filter((request) => request.status === 'PENDING' || request.status === 'APPROVED').sort((left, right) => left.start_date.localeCompare(right.start_date)).map((request) => <button type="button" key={request.id} className={request.status === 'PENDING' ? 'pending-index' : ''} onClick={() => showCalendarDate(request.start_date)}><time>{new Date(request.start_date + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })}</time><span>{request.employee_name}<small>{categories.find((category) => category.id === request.category_id)?.name}</small></span><b>→</b></button>)}{requests.every((request) => request.status !== 'PENDING' && request.status !== 'APPROVED') && <p className="index-empty">No active leave requests.</p>}</div></section>
          </aside>
          <div className="year-calendar">
            <div className="calendar-title"><div><p className="eyebrow">Company calendar</p><h3>{calendarYear}</h3></div><p>Approved leave uses a solid edge. Requests awaiting review use a dashed edge.</p></div>
            <div className="month-grid">{monthNames.map((month, monthIndex) => {
              const firstWeekday = new Date(Date.UTC(calendarYear, monthIndex, 1)).getUTCDay()
              const daysInMonth = new Date(Date.UTC(calendarYear, monthIndex + 1, 0)).getUTCDate()
              return <article className="month-sheet" id={`month-${calendarYear}-${String(monthIndex + 1).padStart(2, '0')}`} tabIndex={-1} key={month}>
                <header><span>{String(monthIndex + 1).padStart(2, '0')}</span><h4>{month}</h4></header>
                <div className="weekday-row">{weekdayNames.map((weekday) => <span key={weekday}>{weekday.slice(0, 1)}</span>)}</div>
                <div className="calendar-days">
                  {Array.from({ length: firstWeekday }, (_, index) => <span className="blank-day" key={'blank-' + index} />)}
                  {Array.from({ length: daysInMonth }, (_, index) => {
                    const day = index + 1
                    const date = `${calendarYear}-${String(monthIndex + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
                    const events = calendarEvents.get(date) ?? []
                    return <div className={`calendar-day${date === today ? ' is-today' : ''}${events.length ? ' has-event' : ''}`} key={date}><span>{day}</span>{events.map((event) => <span title={event.label} className={`day-event event-${event.kind} ${event.status === 'PENDING' ? 'event-pending' : ''}`} key={event.kind + event.id}>{event.kind === 'holiday' ? event.label : event.label.split(' · ')[0]}</span>)}</div>
                  })}
                </div>
              </article>
            })}</div>
          </div>
        </section>}

        {actor?.is_admin && tab === 'people' && <section className="people-layout">
          <form className="content-card group-builder" onSubmit={createGroup}>
            <div className="card-heading"><div><p className="eyebrow">Company structure</p><h3>Create a group</h3><p>Groups can describe employment type, location, team, or any rule your company uses.</p></div></div>
            <Field label="Group name" hint="Examples: Interns, contractors, New York team"><input className={inputClass} aria-label="Group name" value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="e.g. Seasonal employees" required /></Field>
            <button className={buttonClass} disabled={busyAction === 'group-create'}>{busyAction === 'group-create' ? 'Creating…' : 'Create group'}</button>
            <div className="group-registry"><span className="registry-label">Available groups</span>{groups.map((group) => <div key={group.id}><span className="group-glyph">◎</span><span><strong>{group.name}</strong><small>{group.members.length} {group.members.length === 1 ? 'person' : 'people'}</small></span><button className="text-button danger" type="button" aria-label={'Remove ' + group.name} disabled={busyAction === 'group-' + group.id} onClick={() => void removeGroup(group.id)}>×</button></div>)}</div>
          </form>
          <div className="content-card employee-roster">
            <div className="card-heading"><div><p className="eyebrow">Eligibility roster</p><h3>One person, one group</h3><p>Moving someone updates the policies shown on their dashboard from {formatDate(today)}.</p></div><span className="soft-chip">{teamMembers.length} people</span></div>
            <div className="roster-list">{teamMembers.map((employee) => {
              const currentGroup = groups.find((group) => group.members.some((member) => member.employee_id === employee.id))
              return <label className="roster-row" key={employee.id}><span className="mini-avatar">{employee.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span><span className="roster-person"><strong>{employee.name}</strong><small>{employee.employment_type.toLowerCase().replaceAll('_', ' ')}</small></span><span className="assignment-arrow" aria-hidden="true">→</span><select className={inputClass} aria-label={'Group for ' + employee.name} value={currentGroup?.id ?? ''} disabled={busyAction === 'membership-' + employee.id} onChange={(event) => void assignEmployeeGroup(employee.id, event.target.value)}><option value="">Unassigned</option>{groups.map((group) => <option value={group.id} key={group.id}>{group.name}</option>)}</select></label>
            })}</div>
          </div>
        </section>}

        {actor?.is_admin && tab === 'policies' && <><aside className="policy-explainer"><span>POLICY / noun</span><p>The rulebook for one leave type: who receives it, how time is earned, and what happens to unused time.</p></aside><section className="policy-layout">
          <div className="policy-list-column">
            {showCategoryForm && <form onSubmit={createCategory} className="content-card compact-form">
              <div><h3>Add a time-off category</h3><p>Categories group related policies and balances.</p></div>
              <div className="inline-form"><input className={inputClass} aria-label="Category name" value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="e.g. Volunteer leave" required /><button className={buttonClass} disabled={busyAction === 'category'}>{busyAction === 'category' ? 'Creating…' : 'Create'}</button></div>
            </form>}
            <div className="section-heading"><div><h3>Current policies</h3><p>{policies.length} configured</p></div><button className={secondaryButtonClass} type="button" onClick={() => void syncHolidays()} disabled={busyAction === 'holidays'}>{busyAction === 'holidays' ? 'Syncing…' : `Sync ${today.slice(0, 4)} holidays`}</button></div>
            {policies.map((policy) => <article key={policy.id} className="policy-card">
              <div className="policy-card-top"><span className="category-icon">{policy.category_name.slice(0, 1)}</span><div><h3>{policy.name}</h3><p>{policy.category_name}</p></div><span className="version-chip">v{policy.current_version.version_no}</span></div>
              <div className="policy-summary"><strong>{policySummary(policy)}</strong><span>Effective {formatDate(policy.current_version.effective_from)}</span></div>
              <div className="audience-strip"><span>WHO GETS THIS</span><strong>{policy.all_employees ? 'All employees' : policy.group_names.join(' + ') || 'No group selected'}</strong></div>
              <div className="policy-actions"><button className={secondaryButtonClass} type="button" onClick={() => beginPolicyUpdate(policy)} aria-label={'New version for ' + policy.name}>Edit rules & audience</button></div>
              <details onToggle={(event) => { if (event.currentTarget.open) void loadVersions(policy.id) }}><summary>Version history <span>{policy.version_count}</span></summary><ol>{(versions[policy.id] ?? []).map((version) => <li key={version.id}><span>v{version.version_no}</span><div><strong>{formatDate(version.effective_from)}</strong><p>{version.change_reason}</p></div></li>)}</ol></details>
            </article>)}
            {policies.length === 0 && <div className="empty-state"><div>＋</div><h3>Create your first policy</h3><p>Use the policy builder to define how time off is earned.</p></div>}
          </div>

          <form onSubmit={savePolicy} className="content-card policy-builder">
            <div className="card-heading"><div><p className="eyebrow">Policy builder</p><h3>{editingPolicyId ? 'Create future version' : 'New policy'}</h3><p>{editingPolicyId ? 'Past balances keep their original rules.' : 'Start with the essentials; advanced rules are optional.'}</p></div>{editingPolicyId && <button className="icon-button" type="button" aria-label="Cancel policy edit" onClick={cancelPolicyUpdate}>×</button>}</div>
            <fieldset><legend>Basics</legend><div className="form-grid">
              <Field label="Policy name"><input className={inputClass} value={policyName} onChange={(event) => setPolicyName(event.target.value)} aria-label="Policy name" placeholder="Full-time vacation" required /></Field>
              <Field label="Category"><select className={inputClass} value={categoryId} onChange={(event) => setCategoryId(event.target.value)} disabled={Boolean(editingPolicyId)} aria-label="Policy category">{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></Field>
              <Field label="Policy type"><select className={inputClass} value={kind} onChange={(event) => setKind(event.target.value as typeof kind)} aria-label="Policy type"><option value="ACCRUAL">Earned balance</option><option value="UNLIMITED">Unlimited</option></select></Field>
              <Field label="Effective from"><input className={inputClass} type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} required /></Field>
              <Field label="Change reason" hint="Stored in version history"><input className={inputClass} aria-label="Change reason" value={changeReason} onChange={(event) => setChangeReason(event.target.value)} placeholder="Why is this changing?" required /></Field>
            </div></fieldset>
            <fieldset className="audience-builder"><legend>Who gets this policy?</legend>
              <label className="all-employee-choice"><input type="checkbox" aria-label="All employees" checked={allEmployees} onChange={(event) => setAllEmployees(event.target.checked)} /><span><strong>All employees</strong><small>Everyone in the company is included.</small></span></label>
              {!allEmployees && <div className="group-choice-grid">{groups.map((group) => <label key={group.id} className={policyGroupIds.includes(group.id) ? 'group-choice selected' : 'group-choice'}><input type="checkbox" checked={policyGroupIds.includes(group.id)} onChange={() => setPolicyGroupIds((current) => toggleId(current, group.id))} /><span>◎</span><strong>{group.name}</strong><small>{group.members.length} {group.members.length === 1 ? 'person' : 'people'}</small></label>)}{groups.length === 0 && <p>Create a People group before targeting selected employees.</p>}</div>}
              <p className="audience-note">Employees see this leave type automatically when they belong to any selected group.</p>
            </fieldset>
            {kind === 'ACCRUAL' && <fieldset><legend>How time is earned</legend><div className="form-grid">
              <Field label="Accrual method"><select className={inputClass} value={accrualMethod} onChange={(event) => setAccrualMethod(event.target.value as typeof accrualMethod)} aria-label="Accrual method"><option value="TIME">On a schedule</option><option value="HOURS_WORKED">Based on hours worked</option></select></Field>
              <Field label={accrualMethod === 'TIME' ? 'Days earned each period' : 'Hours earned'}><input className={inputClass} type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} aria-label={accrualMethod === 'TIME' ? 'Days per period' : 'Hours earned'} required /></Field>
              {accrualMethod === 'TIME' ? <><Field label="Accrual frequency"><select className={inputClass} value={frequency} onChange={(event) => setFrequency(event.target.value as typeof frequency)} aria-label="Accrual frequency"><option value="DAILY">Daily</option><option value="WEEKLY">Weekly</option><option value="SEMIMONTHLY">Twice monthly</option><option value="BIWEEKLY">Every two weeks</option><option value="MONTHLY">Monthly</option><option value="YEARLY">Yearly</option></select></Field><Field label="New-hire treatment"><select className={inputClass} value={newHireProration} onChange={(event) => setNewHireProration(event.target.value as typeof newHireProration)} aria-label="New-hire accrual"><option value="PRORATE">Prorate first period</option><option value="FULL">Grant full first period</option><option value="NONE">Start next period</option></select></Field></> : <Field label="For every hours worked"><input className={inputClass} type="number" min="0.01" step="0.01" value={perHoursWorked} onChange={(event) => setPerHoursWorked(event.target.value)} aria-label="Hours worked per accrual" required /></Field>}
            </div></fieldset>}
            {kind === 'ACCRUAL' && <div className="advanced-panel"><button type="button" onClick={() => setShowAdvancedPolicy((value) => !value)} aria-expanded={showAdvancedPolicy}><span><strong>Advanced balance rules</strong><small>Caps, carryover, tenure, and overdraft</small></span><span>{showAdvancedPolicy ? '−' : '+'}</span></button>{showAdvancedPolicy && <div className="form-grid advanced-fields">
              <Field label="Maximum balance" hint="Leave blank for no cap"><div className="input-suffix"><input className={inputClass} type="number" min="0.25" step="0.25" value={maxBalance} onChange={(event) => setMaxBalance(event.target.value)} aria-label="Maximum balance hours" /><span>hours</span></div></Field>
              <Field label="Carryover limit" hint="Leave blank for no limit"><div className="input-suffix"><input className={inputClass} type="number" min="0" step="0.25" value={carryoverCap} onChange={(event) => setCarryoverCap(event.target.value)} aria-label="Carryover cap hours" disabled={expires} /><span>hours</span></div></Field>
              <Field label="Tenure tier starts after"><div className="input-suffix"><input className={inputClass} type="number" min="1" value={tenureMonths} onChange={(event) => setTenureMonths(event.target.value)} aria-label="Tenure tier months" /><span>months</span></div></Field>
              <Field label="Tier accrual amount"><input className={inputClass} type="number" min="0.01" step="0.01" value={tenureAmount} onChange={(event) => setTenureAmount(event.target.value)} aria-label="Tenure tier amount" /></Field>
              <label className="check-row"><input type="checkbox" checked={expires} onChange={(event) => setExpires(event.target.checked)} disabled={Boolean(carryoverCap)} /><span><strong>Expire balance yearly</strong><small>Cannot be combined with carryover</small></span></label>
              <label className="check-row"><input aria-label="Allow negative balance" type="checkbox" checked={allowNegative} onChange={(event) => setAllowNegative(event.target.checked)} /><span><strong>Allow a negative balance</strong><small>Set the lowest permitted balance</small></span></label>
              {allowNegative && <Field label="Lowest balance"><div className="input-suffix"><input className={inputClass} type="number" max="-0.25" step="0.25" value={negativeFloor} onChange={(event) => setNegativeFloor(event.target.value)} aria-label="Negative balance floor hours" required /><span>hours</span></div></Field>}
            </div>}</div>}
            <div className="form-actions"><button className={buttonClass} disabled={!categoryId || (!allEmployees && policyGroupIds.length === 0) || busyAction === 'policy'}>{busyAction === 'policy' ? 'Saving…' : editingPolicyId ? 'Schedule new version' : 'Create policy'}</button>{editingPolicyId && <button className={secondaryButtonClass} type="button" onClick={cancelPolicyUpdate}>Cancel</button>}</div>
          </form>
        </section></>}

        {tab === 'requests' && <section className="request-layout">
          {!actor?.is_admin && <form onSubmit={submitRequest} className="content-card request-form">
            <div className="card-heading"><div><p className="eyebrow">New request</p><h3>Plan your time away</h3><p>Choose your dates and preview the balance impact before submitting.</p></div></div>
            <div className="form-grid request-fields">
              <Field label="Time-off type"><select className={inputClass} value={requestCategoryId} onChange={(event) => { setRequestCategoryId(event.target.value); setCustomRequestType(''); setRequestPreview(null) }} aria-label="Time-off category">{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></Field>
              {isOtherRequest && <Field label="What kind of leave?" hint="Your approver will see this label"><input className={inputClass} aria-label="Custom time-off type" value={customRequestType} onChange={(event) => { setCustomRequestType(event.target.value); setRequestPreview(null) }} placeholder="e.g. Bereavement leave" required /></Field>}
              <Field label="Reason" hint="Visible to your approver"><input className={inputClass} aria-label="Request reason" value={requestReason} onChange={(event) => setRequestReason(event.target.value)} placeholder="e.g. Family trip" /></Field>
              <Field label="First day"><input className={inputClass} aria-label="Start date" type="date" min={today} value={requestStart} onChange={(event) => { const value = event.target.value; setRequestStart(value); if (!requestEnd || requestEnd < value) setRequestEnd(value); setRequestPreview(null) }} required /></Field>
              <Field label="Last day"><input className={inputClass} aria-label="End date" type="date" min={requestStart || today} value={requestEnd} onChange={(event) => { setRequestEnd(event.target.value); setRequestPreview(null) }} required /></Field>
            </div>
            <label className="check-row partial-toggle"><input aria-label="Partial-day request" type="checkbox" checked={isPartialDay} onChange={(event) => { setIsPartialDay(event.target.checked); setRequestPreview(null) }} /><span><strong>This is a partial-day request</strong><small>Use this for appointments or part of a shift.</small></span></label>
            {isPartialDay && <div className="partial-fields"><Field label="Hours"><input className={inputClass} aria-label="Partial hours" type="number" min="0" max="23" value={requestHours} onChange={(event) => { setRequestHours(event.target.value); setRequestPreview(null) }} placeholder="0" /></Field><Field label="Minutes"><input className={inputClass} aria-label="Partial minutes" type="number" min="0" max="59" value={requestMinutes} onChange={(event) => { setRequestMinutes(event.target.value); setRequestPreview(null) }} placeholder="0" /></Field></div>}
            {requestPreview && <div className="preview-card" role="status"><span className="preview-icon">✓</span><div><strong>{formatMinutes(requestPreview.total_minutes, actor?.work_minutes_per_day)} requested</strong><p>{requestPreview.days.length} working {requestPreview.days.length === 1 ? 'day' : 'days'} · {formatMinutes(requestPreview.available_minutes, actor?.work_minutes_per_day)} available before this request</p></div></div>}
            <div className="form-actions split-actions"><button className={secondaryButtonClass} type="button" onClick={() => void previewRequest()} disabled={!requestStart || !requestEnd || (isOtherRequest && !customRequestType.trim()) || busyAction === 'preview'}>{busyAction === 'preview' ? 'Calculating…' : 'Preview balance impact'}</button><button className={buttonClass} disabled={!requestStart || !requestEnd || (isOtherRequest && !customRequestType.trim()) || busyAction === 'request'}>{busyAction === 'request' ? 'Submitting…' : 'Submit request'}</button></div>
          </form>}
          <div className="content-card request-list">
            <div className="card-heading"><div><p className="eyebrow">{actor?.is_admin ? 'Team requests' : 'Your activity'}</p><h3>{actor?.is_admin ? 'Approval queue' : 'Request history'}</h3><p>{actor?.is_admin ? `${pendingRequests.length} awaiting a decision` : 'Every request and its current status'}</p></div>{actor?.is_admin && pendingRequests.length > 0 && <span className="soft-chip">{pendingRequests.length} pending</span>}</div>
            <div className="request-items">{requests.map((request) => <article key={request.id} className="request-item">
              <div className="request-date"><strong>{new Date(request.start_date + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' })}</strong><span>{new Date(request.start_date + 'T00:00:00Z').getUTCDate()}</span></div>
              <div className="request-details"><div><strong>{actor?.is_admin ? request.employee_name : categories.find((category) => category.id === request.category_id)?.name || 'Time off'}</strong><StatusPill status={request.status} /></div><p>{actor?.is_admin && `${categories.find((category) => category.id === request.category_id)?.name || 'Time off'} · `}{formatDate(request.start_date)}{request.end_date !== request.start_date ? ` – ${formatDate(request.end_date)}` : ''} · {formatMinutes(request.total_minutes, actor?.work_minutes_per_day)}</p>{request.reason && <span>“{request.reason}”</span>}<details><summary>View history ({request.events.length})</summary>{request.events.map((event) => <p key={event.at}>{event.from_status ?? 'Created'} → {event.to_status} · {formatDate(event.at.slice(0, 10))}</p>)}</details></div>
              {actor?.is_admin && request.status === 'PENDING' && <div className="request-actions"><button className={buttonClass} disabled={Boolean(busyAction)} onClick={() => void decide(request.id, 'approve')}>{busyAction === 'approve-' + request.id ? 'Approving…' : 'Approve'}</button><button className={secondaryButtonClass} disabled={Boolean(busyAction)} onClick={() => void decide(request.id, 'deny')}>{busyAction === 'deny-' + request.id ? 'Denying…' : 'Deny'}</button></div>}
              {!actor?.is_admin && (request.status === 'PENDING' || request.status === 'APPROVED') && <button className="text-button danger" type="button" disabled={Boolean(busyAction)} onClick={() => void cancelRequest(request.id)}>{busyAction === 'cancel-' + request.id ? 'Cancelling…' : 'Cancel request'}</button>}
            </article>)}</div>
            {requests.length === 0 && <div className="empty-state"><div>✓</div><h3>{actor?.is_admin ? 'Approval queue is clear' : 'No requests yet'}</h3><p>{actor?.is_admin ? 'There are no requests waiting for a decision.' : 'Submitted requests will appear here.'}</p></div>}
          </div>
        </section>}

        {actor?.is_admin && tab === 'audit' && <section className="audit-layout">
          <div className="content-card">
            <div className="card-heading"><div><p className="eyebrow">Balance ledger</p><h3>Explain a balance</h3><p>Every adjustment is recorded in chronological order.</p></div><select className={inputClass} aria-label="Employee to audit" value={auditEmployeeId} onChange={(event) => setAuditEmployeeId(event.target.value)}>{employees.filter((employee) => !employee.is_admin).map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></div>
            <div className="table-wrap"><table><thead><tr><th>Date</th><th>Entry</th><th>Source</th><th>Change</th><th>Running balance</th></tr></thead><tbody>{runningLedger.map((entry) => <tr key={entry.id}><td>{formatDate(entry.effective_date)}</td><td><span className="entry-chip">{entry.entry_type.toLowerCase().replaceAll('_', ' ')}</span></td><td>{entry.note ?? entry.source_type.toLowerCase().replaceAll('_', ' ')}</td><td className={entry.amount_minutes >= 0 ? 'positive-value' : 'negative-value'}>{entry.amount_minutes >= 0 ? '+' : ''}{formatMinutes(entry.amount_minutes, selectedAuditEmployee?.work_minutes_per_day)}</td><td><strong>{formatMinutes(entry.running, selectedAuditEmployee?.work_minutes_per_day)}</strong></td></tr>)}</tbody></table></div>
            {ledger.length === 0 && <div className="empty-state"><div>≡</div><h3>No balance activity</h3><p>This employee does not have any ledger entries yet.</p></div>}
          </div>
          <div className="content-card job-card"><div className="card-heading"><div><p className="eyebrow">Operations</p><h3>Recent job runs</h3></div></div>{jobRuns.map((run) => <div className="job-row" key={run.id}><span className="job-icon">↻</span><div><strong>{run.kind.toLowerCase()} run</strong><p>{run.source_id}</p></div><StatusPill status={run.status} /><span>{run.entries_created} entries</span></div>)}{jobRuns.length === 0 && <p className="muted-copy">No background jobs have run yet.</p>}</div>
        </section>}

      </main>
    </div>
  )
}
