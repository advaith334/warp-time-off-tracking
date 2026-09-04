import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, api, setActor } from './api/client'
import type {
  Balance,
  Category,
  Employee,
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
type Tab = 'overview' | 'requests' | 'policies' | 'audit' | 'demo'

const tabDescriptions: Record<Tab, string> = {
  overview: 'Balances and policy coverage at a glance',
  requests: 'Submit, review, and track time-off requests',
  policies: 'Configure accrual and eligibility rules',
  audit: 'Follow every balance change back to its source',
  demo: 'Move time forward and run background jobs',
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

function dayAfter(value: string) {
  const result = new Date(value + 'T00:00:00Z')
  result.setUTCDate(result.getUTCDate() + 1)
  return result.toISOString().slice(0, 10)
}

export default function App() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [policies, setPolicies] = useState<Policy[]>([])
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
  const [demoDate, setDemoDate] = useState('')
  const [demoResult, setDemoResult] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [showAdvancedPolicy, setShowAdvancedPolicy] = useState(false)
  const [categoryName, setCategoryName] = useState('')
  const [policyName, setPolicyName] = useState('')
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
  const [isPartialDay, setIsPartialDay] = useState(false)
  const [requestHours, setRequestHours] = useState('')
  const [requestMinutes, setRequestMinutes] = useState('')
  const [requestPreview, setRequestPreview] = useState<RequestPreview | null>(null)

  const actor = employees.find((employee) => employee.id === actorId)
  const selectedAuditEmployee = employees.find((employee) => employee.id === auditEmployeeId)
  const pendingRequests = requests.filter((request) => request.status === 'PENDING')
  const tabs: Array<{ id: Tab; label: string }> = actor?.is_admin
    ? [
        { id: 'overview', label: 'Overview' },
        { id: 'policies', label: 'Policies' },
        { id: 'requests', label: 'Approvals' },
        { id: 'audit', label: 'Audit' },
        { id: 'demo', label: 'Demo' },
      ]
    : [
        { id: 'overview', label: 'My time off' },
        { id: 'requests', label: 'My requests' },
      ]

  async function load() {
    try {
      const [people, cats, policyRows, state] = await Promise.all([
        api.get<Employee[]>('/employees'),
        api.get<Category[]>('/categories'),
        api.get<Policy[]>('/policies'),
        api.get<{ today: string }>('/dev/state'),
      ])
      const holidayRows = await api.get<Holiday[]>('/holidays?year=' + state.today.slice(0, 4))
      setEmployees(people)
      setCategories(cats)
      setPolicies(policyRows)
      setHolidays(holidayRows)
      setToday(state.today)
      setDemoDate(state.today)
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
        await api.post('/policies', { ...policyFields, category_id: categoryId })
      }
      setPolicyName('')
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
    setChangeReason('Policy created')
    setEffectiveFrom(today)
  }

  async function syncHolidays() {
    await perform('holidays', 'Holiday calendar synchronized.', async () => {
      setHolidays(await api.post<Holiday[]>('/holidays/sync?year=' + today.slice(0, 4)))
    })
  }

  async function assign(policyId: string, employeeId: string) {
    await perform('assignment', 'Employee assigned to policy.', async () => {
      await api.post('/policies/' + policyId + '/assignments', {
        employee_ids: [employeeId], effective_from: today,
      })
    })
  }

  async function loadVersions(policyId: string) {
    if (versions[policyId]) return
    const rows = await api.get<PolicyVersion[]>('/policies/' + policyId + '/versions')
    setVersions((current) => ({ ...current, [policyId]: rows }))
  }

  function requestPayload() {
    return {
      employee_id: actorId, category_id: requestCategoryId, reason: requestReason || 'Time off',
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

  async function setClock() {
    await perform('clock', 'Demo date updated.', async () => {
      const state = await api.post<{ today: string }>('/dev/clock', { current_date: demoDate })
      setToday(state.today)
      setDemoResult('Demo date moved to ' + formatDate(state.today) + '.')
    })
  }

  async function runJob(kind: 'accruals' | 'rollover') {
    await perform(kind, `${kind === 'accruals' ? 'Accrual' : 'Rollover'} job completed.`, async () => {
      const run = await api.post<JobRun>('/dev/' + kind)
      setDemoResult(`${run.kind.toLowerCase()} finished · ${run.entries_created} ledger entries created`)
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

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true"><span /></div>
            <div>
              <p className="eyebrow">Northstar / People ops</p>
              <h1>Time-off policies</h1>
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
                {employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}{employee.is_admin ? ' (admin)' : ''}</option>)}
              </select>
            </label>
          </div>
        </div>
        <div className="nav-wrap">
          <nav aria-label="Product sections">
            {tabs.map((item, index) => <button key={item.id} type="button" aria-current={tab === item.id ? 'page' : undefined} onClick={() => {
              setTab(item.id)
              setError('')
              setSuccess('')
            }}><span className="nav-index" aria-hidden="true">0{index + 1}</span>{item.label}{item.id === 'requests' && actor?.is_admin && pendingRequests.length > 0 && <span className="nav-count" aria-hidden="true">{pendingRequests.length}</span>}</button>)}
          </nav>
          {today && <span className="date-chip"><span aria-hidden="true">SIM</span>{formatDate(today)}</span>}
        </div>
      </header>

      <main className="page-content">
        <div className="page-heading">
          <div>
            <p className="eyebrow">{actor?.is_admin ? 'Admin workspace' : 'Employee workspace'}</p>
            <h2>{tabs.find((item) => item.id === tab)?.label}</h2>
            <p>{tabDescriptions[tab]}</p>
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
            <article className="stat-card accent-amber"><span>Holiday calendar</span><strong>{holidays.length}</strong><p>Observed holidays loaded for {today.slice(0, 4)}</p><button type="button" onClick={() => setTab('policies')}>Review calendar →</button></article>
            <article className="content-card dashboard-wide">
              <div className="card-heading"><div><p className="eyebrow">Team snapshot</p><h3>Policy coverage</h3></div><span className="soft-chip">{employees.filter((employee) => !employee.is_admin).length} employees</span></div>
              <div className="coverage-list">{policies.map((policy) => <div key={policy.id}><span className="category-icon">{policy.category_name.slice(0, 1)}</span><div><strong>{policy.name}</strong><p>{policySummary(policy)}</p></div><span className="version-chip">v{policy.current_version.version_no}</span></div>)}</div>
            </article>
          </section>
        )}

        {!loading && tab === 'overview' && !actor?.is_admin && (
          <section className="balance-grid">
            {balances.map((balance, index) => <article key={balance.category_id} className={`balance-card balance-${index % 3}`}>
              <div className="balance-top"><span className="category-icon">{balance.category_name.slice(0, 1)}</span><span className="soft-chip">{balance.has_policy ? balance.policy_name : 'Not enrolled'}</span></div>
              <p>{balance.category_name}</p>
              <strong>{!balance.has_policy ? 'No policy' : balance.is_unlimited ? 'Unlimited' : formatMinutes(balance.available_minutes, balance.day_minutes)}</strong>
              <span>{!balance.has_policy ? 'Ask an administrator to assign a policy' : balance.is_unlimited ? 'No balance limit' : 'available to request'}</span>
              {balance.pending_hold_minutes > 0 && <div className="pending-note"><span />{formatMinutes(balance.pending_hold_minutes, balance.day_minutes)} awaiting approval</div>}
            </article>)}
            {balances.length === 0 && <div className="empty-state"><div>◌</div><h3>No time-off categories yet</h3><p>Your administrator has not configured any categories.</p></div>}
          </section>
        )}

        {actor?.is_admin && tab === 'policies' && <section className="policy-layout">
          <div className="policy-list-column">
            {showCategoryForm && <form onSubmit={createCategory} className="content-card compact-form">
              <div><h3>Add a time-off category</h3><p>Categories group related policies and balances.</p></div>
              <div className="inline-form"><input className={inputClass} aria-label="Category name" value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="e.g. Volunteer leave" required /><button className={buttonClass} disabled={busyAction === 'category'}>{busyAction === 'category' ? 'Creating…' : 'Create'}</button></div>
            </form>}
            <div className="section-heading"><div><h3>Current policies</h3><p>{policies.length} configured</p></div><button className={secondaryButtonClass} type="button" onClick={() => void syncHolidays()} disabled={busyAction === 'holidays'}>{busyAction === 'holidays' ? 'Syncing…' : `Sync ${today.slice(0, 4)} holidays`}</button></div>
            {policies.map((policy) => <article key={policy.id} className="policy-card">
              <div className="policy-card-top"><span className="category-icon">{policy.category_name.slice(0, 1)}</span><div><h3>{policy.name}</h3><p>{policy.category_name}</p></div><span className="version-chip">v{policy.current_version.version_no}</span></div>
              <div className="policy-summary"><strong>{policySummary(policy)}</strong><span>Effective {formatDate(policy.current_version.effective_from)}</span></div>
              <div className="policy-actions"><button className={secondaryButtonClass} type="button" onClick={() => beginPolicyUpdate(policy)} aria-label={'New version for ' + policy.name}>Edit policy</button><select className={inputClass} defaultValue="" disabled={busyAction === 'assignment'} onChange={(event) => { if (event.target.value) void assign(policy.id, event.target.value); event.target.value = '' }} aria-label={'Assign employee to ' + policy.name}><option value="">Assign employee…</option>{employees.filter((employee) => !employee.is_admin).map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></div>
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
            <div className="form-actions"><button className={buttonClass} disabled={!categoryId || busyAction === 'policy'}>{busyAction === 'policy' ? 'Saving…' : editingPolicyId ? 'Schedule new version' : 'Create policy'}</button>{editingPolicyId && <button className={secondaryButtonClass} type="button" onClick={cancelPolicyUpdate}>Cancel</button>}</div>
          </form>
        </section>}

        {tab === 'requests' && <section className="request-layout">
          {!actor?.is_admin && <form onSubmit={submitRequest} className="content-card request-form">
            <div className="card-heading"><div><p className="eyebrow">New request</p><h3>Plan your time away</h3><p>Choose your dates and preview the balance impact before submitting.</p></div></div>
            <div className="form-grid request-fields">
              <Field label="Time-off type"><select className={inputClass} value={requestCategoryId} onChange={(event) => { setRequestCategoryId(event.target.value); setRequestPreview(null) }} aria-label="Time-off category">{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></Field>
              <Field label="Reason" hint="Visible to your approver"><input className={inputClass} aria-label="Request reason" value={requestReason} onChange={(event) => setRequestReason(event.target.value)} placeholder="e.g. Family trip" /></Field>
              <Field label="First day"><input className={inputClass} aria-label="Start date" type="date" min={today} value={requestStart} onChange={(event) => { const value = event.target.value; setRequestStart(value); if (!requestEnd || requestEnd < value) setRequestEnd(value); setRequestPreview(null) }} required /></Field>
              <Field label="Last day"><input className={inputClass} aria-label="End date" type="date" min={requestStart || today} value={requestEnd} onChange={(event) => { setRequestEnd(event.target.value); setRequestPreview(null) }} required /></Field>
            </div>
            <label className="check-row partial-toggle"><input aria-label="Partial-day request" type="checkbox" checked={isPartialDay} onChange={(event) => { setIsPartialDay(event.target.checked); setRequestPreview(null) }} /><span><strong>This is a partial-day request</strong><small>Use this for appointments or part of a shift.</small></span></label>
            {isPartialDay && <div className="partial-fields"><Field label="Hours"><input className={inputClass} aria-label="Partial hours" type="number" min="0" max="23" value={requestHours} onChange={(event) => { setRequestHours(event.target.value); setRequestPreview(null) }} placeholder="0" /></Field><Field label="Minutes"><input className={inputClass} aria-label="Partial minutes" type="number" min="0" max="59" value={requestMinutes} onChange={(event) => { setRequestMinutes(event.target.value); setRequestPreview(null) }} placeholder="0" /></Field></div>}
            {requestPreview && <div className="preview-card" role="status"><span className="preview-icon">✓</span><div><strong>{formatMinutes(requestPreview.total_minutes, actor?.work_minutes_per_day)} requested</strong><p>{requestPreview.days.length} working {requestPreview.days.length === 1 ? 'day' : 'days'} · {formatMinutes(requestPreview.available_minutes, actor?.work_minutes_per_day)} available before this request</p></div></div>}
            <div className="form-actions split-actions"><button className={secondaryButtonClass} type="button" onClick={() => void previewRequest()} disabled={!requestStart || !requestEnd || busyAction === 'preview'}>{busyAction === 'preview' ? 'Calculating…' : 'Preview balance impact'}</button><button className={buttonClass} disabled={!requestStart || !requestEnd || busyAction === 'request'}>{busyAction === 'request' ? 'Submitting…' : 'Submit request'}</button></div>
          </form>}
          <div className="content-card request-list">
            <div className="card-heading"><div><p className="eyebrow">{actor?.is_admin ? 'Team requests' : 'Your activity'}</p><h3>{actor?.is_admin ? 'Approval queue' : 'Request history'}</h3><p>{actor?.is_admin ? `${pendingRequests.length} awaiting a decision` : 'Every request and its current status'}</p></div>{actor?.is_admin && pendingRequests.length > 0 && <span className="soft-chip">{pendingRequests.length} pending</span>}</div>
            <div className="request-items">{requests.map((request) => <article key={request.id} className="request-item">
              <div className="request-date"><strong>{new Date(request.start_date + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' })}</strong><span>{new Date(request.start_date + 'T00:00:00Z').getUTCDate()}</span></div>
              <div className="request-details"><div><strong>{actor?.is_admin ? request.employee_name : categories.find((category) => category.id === request.category_id)?.name || 'Time off'}</strong><StatusPill status={request.status} /></div><p>{formatDate(request.start_date)}{request.end_date !== request.start_date ? ` – ${formatDate(request.end_date)}` : ''} · {formatMinutes(request.total_minutes, actor?.work_minutes_per_day)}</p>{request.reason && <span>“{request.reason}”</span>}<details><summary>View history ({request.events.length})</summary>{request.events.map((event) => <p key={event.at}>{event.from_status ?? 'Created'} → {event.to_status} · {formatDate(event.at.slice(0, 10))}</p>)}</details></div>
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

        {actor?.is_admin && tab === 'demo' && <section className="demo-grid">
          <article className="content-card demo-card"><span className="step-number">1</span><div><h3>Choose a simulated date</h3><p>Move the demo clock without changing your computer’s date.</p><Field label="Demo date"><input className={inputClass} aria-label="Demo date" type="date" value={demoDate} onChange={(event) => setDemoDate(event.target.value)} /></Field><button className={buttonClass} disabled={busyAction === 'clock'} onClick={() => void setClock()}>{busyAction === 'clock' ? 'Updating…' : 'Set demo date'}</button></div></article>
          <article className="content-card demo-card"><span className="step-number">2</span><div><h3>Run accruals</h3><p>Post every scheduled credit due through the selected date.</p><button className={buttonClass} disabled={busyAction === 'accruals'} onClick={() => void runJob('accruals')}>{busyAction === 'accruals' ? 'Running…' : 'Run accrual job'}</button></div></article>
          <article className="content-card demo-card"><span className="step-number">3</span><div><h3>Run year-end rollover</h3><p>Apply carryover caps or expiry rules for completed periods.</p><button className={secondaryButtonClass} disabled={busyAction === 'rollover'} onClick={() => void runJob('rollover')}>{busyAction === 'rollover' ? 'Running…' : 'Run rollover job'}</button></div></article>
          {demoResult && <div className="demo-result"><span>✓</span><p>{demoResult}</p></div>}
        </section>}
      </main>
    </div>
  )
}
