import { useEffect, useMemo, useState } from 'react'
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

const inputClass = 'rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm'
const buttonClass = 'rounded-lg bg-neutral-900 px-3 py-2 text-sm font-medium text-white'
type Tab = 'overview' | 'requests' | 'policies' | 'audit' | 'demo'

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
  const [categoryName, setCategoryName] = useState('')
  const [policyName, setPolicyName] = useState('')
  const [editingPolicyId, setEditingPolicyId] = useState<string | null>(null)
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [changeReason, setChangeReason] = useState('Policy created')
  const [kind, setKind] = useState<'ACCRUAL' | 'UNLIMITED'>('ACCRUAL')
  const [amount, setAmount] = useState('20')
  const [newHireProration, setNewHireProration] = useState<'PRORATE' | 'FULL' | 'NONE'>('PRORATE')
  const [allowNegative, setAllowNegative] = useState(false)
  const [negativeFloor, setNegativeFloor] = useState('-480')
  const [tenureMonths, setTenureMonths] = useState('')
  const [tenureAmount, setTenureAmount] = useState('')
  const [maxBalance, setMaxBalance] = useState('')
  const [carryoverCap, setCarryoverCap] = useState('')
  const [expires, setExpires] = useState(false)
  const [categoryId, setCategoryId] = useState('')
  const [requestCategoryId, setRequestCategoryId] = useState('')
  const [requestStart, setRequestStart] = useState('')
  const [requestEnd, setRequestEnd] = useState('')
  const [requestHours, setRequestHours] = useState('')
  const [requestMinutes, setRequestMinutes] = useState('')
  const [requestPreview, setRequestPreview] = useState<RequestPreview | null>(null)

  const actor = employees.find((employee) => employee.id === actorId)
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

  async function createCategory(event: React.FormEvent) {
    event.preventDefault()
    await api.post('/categories', { name: categoryName })
    setCategoryName('')
    await load()
  }

  async function savePolicy(event: React.FormEvent) {
    event.preventDefault()
    const rules = kind === 'UNLIMITED' ? [] : [
      {
        method: 'TIME', amount, unit: 'DAY', frequency: 'YEARLY',
        accrues_at: 'START_OF_PERIOD', min_tenure_months: 0,
      },
      ...(tenureMonths && tenureAmount ? [{
        method: 'TIME', amount: tenureAmount, unit: 'DAY', frequency: 'YEARLY',
        accrues_at: 'START_OF_PERIOD', min_tenure_months: Number(tenureMonths),
      }] : []),
    ]
    const policyFields = {
      name: policyName, effective_from: effectiveFrom, kind, rules,
      change_reason: changeReason,
      new_hire_proration: newHireProration,
      allow_negative: allowNegative,
      negative_floor_minutes: allowNegative ? Number(negativeFloor) : 0,
      max_balance_minutes: maxBalance ? Number(maxBalance) : null,
      carryover_cap_minutes: carryoverCap ? Number(carryoverCap) : null,
      expires_at_period_end: expires, tenure_transition: 'NEXT_PERIOD',
    }
    if (editingPolicyId) {
      await api.put('/policies/' + editingPolicyId, policyFields)
    } else {
      await api.post('/policies', { ...policyFields, category_id: categoryId })
    }
    setPolicyName('')
    setEditingPolicyId(null)
    setChangeReason('Policy created')
    setVersions({})
    await load()
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
    setAmount(base?.amount ?? '20')
    setNewHireProration(policy.current_version.new_hire_proration)
    setAllowNegative(policy.current_version.allow_negative)
    setNegativeFloor(String(policy.current_version.negative_floor_minutes || -480))
    setMaxBalance(policy.current_version.max_balance_minutes?.toString() ?? '')
    setCarryoverCap(policy.current_version.carryover_cap_minutes?.toString() ?? '')
    setExpires(policy.current_version.expires_at_period_end)
    setTenureMonths(tier?.min_tenure_months.toString() ?? '')
    setTenureAmount(tier?.amount ?? '')
  }

  function cancelPolicyUpdate() {
    setEditingPolicyId(null)
    setPolicyName('')
    setChangeReason('Policy created')
    setEffectiveFrom(today)
  }

  async function syncHolidays() {
    setHolidays(await api.post<Holiday[]>('/holidays/sync?year=' + today.slice(0, 4)))
  }

  async function assign(policyId: string, employeeId: string) {
    await api.post('/policies/' + policyId + '/assignments', {
      employee_ids: [employeeId], effective_from: today,
    })
    setDemoResult('Assignment saved.')
  }

  async function loadVersions(policyId: string) {
    if (versions[policyId]) return
    const rows = await api.get<PolicyVersion[]>('/policies/' + policyId + '/versions')
    setVersions((current) => ({ ...current, [policyId]: rows }))
  }

  function requestPayload() {
    return {
      employee_id: actorId, category_id: requestCategoryId, reason: 'Time off',
      start_date: requestStart, end_date: requestEnd,
      hours: requestHours === '' ? null : Number(requestHours),
      minutes: requestMinutes === '' ? null : Number(requestMinutes),
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
    try {
      setRequestPreview(await api.post<RequestPreview>('/requests/preview', requestPayload()))
      setError('')
    } catch (caught) {
      setRequestPreview(null)
      setError(caught instanceof ApiError ? caught.message : String(caught))
    }
  }

  async function submitRequest(event: React.FormEvent) {
    event.preventDefault()
    try {
      await api.post('/requests', requestPayload())
      setRequestPreview(null)
      await refreshSelfService()
      setError('')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    }
  }

  async function cancelRequest(requestId: string) {
    try {
      await api.post('/requests/' + requestId + '/cancel')
      await refreshSelfService()
      setError('')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    }
  }

  async function decide(requestId: string, action: 'approve' | 'deny') {
    await api.post('/requests/' + requestId + '/' + action, {})
    setRequests(await api.get<TimeOffRequest[]>('/requests'))
  }

  async function setClock() {
    const state = await api.post<{ today: string }>('/dev/clock', { current_date: demoDate })
    setToday(state.today)
    setDemoResult('Demo date moved to ' + state.today + '.')
  }

  async function runJob(kind: 'accruals' | 'rollover') {
    const run = await api.post<JobRun>('/dev/' + kind)
    setDemoResult(`${run.kind} finished: ${run.entries_created} ledger entries created.`)
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
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-neutral-500">Northstar Robotics</p>
          <h1 className="mt-1 text-3xl font-semibold">Time-off policies</h1>
          {today && <p className="mt-1 text-xs text-neutral-500">Demo date: {today}</p>}
        </div>
        <label className="text-xs text-neutral-600">
          Acting as
          <select className={inputClass + ' ml-2'} value={actorId} onChange={(event) => {
            setActorId(event.target.value)
            setActor(event.target.value)
            setTab('overview')
          }}>
            {employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}{employee.is_admin ? ' (admin)' : ''}</option>)}
          </select>
        </label>
      </header>

      <nav className="flex flex-wrap gap-2" aria-label="Product sections">
        {tabs.map((item) => <button key={item.id} className={tab === item.id ? buttonClass : inputClass} onClick={() => setTab(item.id)}>{item.label}</button>)}
      </nav>

      {loading && <p className="rounded-xl border bg-white p-6 text-sm text-neutral-500">Loading time-off data…</p>}
      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}

      {!loading && tab === 'overview' && (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {balances.map((balance) => <article key={balance.category_id} className="rounded-xl border bg-white p-5">
            <p className="text-sm font-medium">{balance.category_name}</p>
            <p className="mt-2 text-2xl font-semibold">{!balance.has_policy ? 'No policy set' : balance.is_unlimited ? 'Unlimited' : (balance.balance_minutes / balance.day_minutes).toFixed(2) + ' days'}</p>
            {balance.policy_name && <p className="mt-1 text-xs text-neutral-500">{balance.policy_name}</p>}
            {balance.pending_hold_minutes > 0 && <p className="mt-2 text-xs text-amber-700">{balance.pending_hold_minutes} minutes pending</p>}
          </article>)}
          {balances.length === 0 && <p className="text-sm text-neutral-500">No categories configured.</p>}
        </section>
      )}

      {actor?.is_admin && tab === 'policies' && <>
        <section className="grid gap-4 rounded-xl border bg-white p-5 md:grid-cols-2">
          <form onSubmit={createCategory} className="space-y-3"><h2 className="font-semibold">Add category</h2><input className={inputClass + ' w-full'} value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="Vacation" required /><button className={buttonClass}>Create category</button></form>
          <form onSubmit={savePolicy} className="space-y-3">
            <h2 className="font-semibold">{editingPolicyId ? 'Create future version' : 'Add policy'}</h2>
            <input className={inputClass + ' w-full'} value={policyName} onChange={(event) => setPolicyName(event.target.value)} aria-label="Policy name" placeholder="Full-time vacation" required />
            <div className="grid grid-cols-2 gap-2"><select className={inputClass} value={categoryId} onChange={(event) => setCategoryId(event.target.value)} disabled={Boolean(editingPolicyId)} aria-label="Policy category">{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select><select className={inputClass} value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}><option value="ACCRUAL">Accrual</option><option value="UNLIMITED">Unlimited</option></select></div>
            <div className="grid grid-cols-2 gap-2"><label className="text-xs text-neutral-600">Effective from<input className={inputClass + ' mt-1 w-full'} type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} required /></label><label className="text-xs text-neutral-600">Change reason<input className={inputClass + ' mt-1 w-full'} value={changeReason} onChange={(event) => setChangeReason(event.target.value)} placeholder="Why is this changing?" required /></label></div>
            {kind === 'ACCRUAL' && <div className="grid grid-cols-2 gap-2">
              <input className={inputClass} type="number" min="1" value={amount} onChange={(event) => setAmount(event.target.value)} aria-label="Days per year" placeholder="Days per year" />
              <select className={inputClass} value={newHireProration} onChange={(event) => setNewHireProration(event.target.value as typeof newHireProration)} aria-label="New-hire accrual"><option value="PRORATE">Prorate new hires</option><option value="FULL">Full first period</option><option value="NONE">Start next period</option></select>
              <input className={inputClass} type="number" min="1" value={maxBalance} onChange={(event) => setMaxBalance(event.target.value)} aria-label="Maximum balance minutes" placeholder="Max balance minutes" />
              <input className={inputClass} type="number" min="0" value={carryoverCap} onChange={(event) => setCarryoverCap(event.target.value)} aria-label="Carryover cap minutes" placeholder="Carryover cap minutes" disabled={expires} />
              <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={expires} onChange={(event) => setExpires(event.target.checked)} disabled={Boolean(carryoverCap)} /> Expire yearly</label>
              <input className={inputClass} type="number" min="1" value={tenureMonths} onChange={(event) => setTenureMonths(event.target.value)} aria-label="Tenure tier months" placeholder="Tier after months" />
              <input className={inputClass} type="number" min="1" value={tenureAmount} onChange={(event) => setTenureAmount(event.target.value)} aria-label="Tenure tier days" placeholder="Tier days/year" />
              <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={allowNegative} onChange={(event) => setAllowNegative(event.target.checked)} /> Allow negative balance</label>
              <input className={inputClass} type="number" max="-1" value={negativeFloor} onChange={(event) => setNegativeFloor(event.target.value)} aria-label="Negative balance floor minutes" placeholder="Negative floor minutes" disabled={!allowNegative} required={allowNegative} />
            </div>}
            <div className="flex gap-2"><button className={buttonClass} disabled={!categoryId}>{editingPolicyId ? 'Save new version' : 'Create policy'}</button>{editingPolicyId && <button className={inputClass} type="button" onClick={cancelPolicyUpdate}>Cancel edit</button>}</div>
          </form>
          <div className="flex items-center justify-between gap-3 md:col-span-2"><p className="text-sm text-neutral-600">{holidays.length ? `${holidays.length} holidays loaded` : 'No holidays loaded.'}</p><button className={buttonClass} type="button" onClick={() => void syncHolidays()}>Sync observed holidays</button></div>
        </section>
        <section className="space-y-3">
          {policies.map((policy) => <article key={policy.id} className="rounded-xl border bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="font-semibold">{policy.name}</h2><p className="text-sm text-neutral-500">{policy.category_name} · {policy.current_version.kind.toLowerCase()} · v{policy.current_version.version_no}</p></div><div className="flex flex-wrap gap-2"><button className={inputClass} type="button" onClick={() => beginPolicyUpdate(policy)} aria-label={'New version for ' + policy.name}>New version</button><select className={inputClass} defaultValue="" onChange={(event) => { if (event.target.value) void assign(policy.id, event.target.value) }} aria-label={'Assign employee to ' + policy.name}><option value="">Assign employee…</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></div></div>
            <details className="mt-3 text-xs text-neutral-600" onToggle={(event) => { if (event.currentTarget.open) void loadVersions(policy.id) }}><summary className="cursor-pointer">Version history ({policy.version_count})</summary><ul className="mt-2 space-y-1">{(versions[policy.id] ?? []).map((version) => <li key={version.id}>v{version.version_no} from {version.effective_from} · {version.change_reason} · by {version.created_by}</li>)}</ul></details>
          </article>)}
          {policies.length === 0 && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-neutral-500">No policies yet.</p>}
        </section>
      </>}

      {tab === 'requests' && <section className="space-y-4">
        {!actor?.is_admin && <form onSubmit={submitRequest} className="grid gap-3 rounded-xl border bg-white p-5 sm:grid-cols-2 lg:grid-cols-4"><select className={inputClass} value={requestCategoryId} onChange={(event) => { setRequestCategoryId(event.target.value); setRequestPreview(null) }} aria-label="Time-off category">{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select><input className={inputClass} aria-label="Start date" type="date" value={requestStart} onChange={(event) => { setRequestStart(event.target.value); setRequestPreview(null) }} required /><input className={inputClass} aria-label="End date" type="date" value={requestEnd} onChange={(event) => { setRequestEnd(event.target.value); setRequestPreview(null) }} required /><div className="grid grid-cols-2 gap-2"><input className={inputClass} aria-label="Partial hours" type="number" min="0" max="23" value={requestHours} onChange={(event) => { setRequestHours(event.target.value); setRequestPreview(null) }} placeholder="Hours" /><input className={inputClass} aria-label="Partial minutes" type="number" min="0" max="59" value={requestMinutes} onChange={(event) => { setRequestMinutes(event.target.value); setRequestPreview(null) }} placeholder="Minutes" /></div><button className={inputClass} type="button" onClick={() => void previewRequest()} disabled={!requestStart || !requestEnd}>Preview request</button><button className={buttonClass}>Request time off</button>{requestPreview && <p className="self-center text-sm text-neutral-600 sm:col-span-2">{requestPreview.total_minutes} minutes across {requestPreview.days.length} working day{requestPreview.days.length === 1 ? '' : 's'} · {requestPreview.available_minutes} available before this request</p>}</form>}
        <div className="rounded-xl border bg-white"><h2 className="border-b px-5 py-4 font-semibold">{actor?.is_admin ? 'Approval queue' : 'Request history'}</h2>{requests.map((request) => <div key={request.id} className="border-b px-5 py-3 text-sm last:border-0"><div className="flex flex-wrap items-center gap-3"><span className="font-medium">{request.employee_name}</span><span className="text-neutral-500">{request.start_date} to {request.end_date}</span><span className="rounded-full bg-neutral-100 px-2 py-1 text-xs">{request.status.toLowerCase()}</span>{actor?.is_admin && request.status === 'PENDING' && <span className="ml-auto flex gap-2"><button className={buttonClass} onClick={() => void decide(request.id, 'approve')}>Approve</button><button className={inputClass} onClick={() => void decide(request.id, 'deny')}>Deny</button></span>}{!actor?.is_admin && (request.status === 'PENDING' || request.status === 'APPROVED') && <button className={inputClass + ' ml-auto'} type="button" onClick={() => void cancelRequest(request.id)}>Cancel request</button>}</div><details className="mt-2 text-xs text-neutral-500"><summary>History ({request.events.length})</summary>{request.events.map((event) => <p key={event.at} className="mt-1">{event.from_status ?? 'Created'} → {event.to_status} by {event.actor_id}</p>)}</details></div>)}{requests.length === 0 && <p className="p-5 text-sm text-neutral-500">No requests.</p>}</div>
      </section>}

      {actor?.is_admin && tab === 'audit' && <section className="space-y-4">
        <div className="flex items-center gap-3"><h2 className="font-semibold">Explain a balance</h2><select className={inputClass} value={auditEmployeeId} onChange={(event) => setAuditEmployeeId(event.target.value)}>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></div>
        <div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full text-left text-xs"><thead><tr className="border-b"><th className="p-3">Date</th><th>Entry</th><th>Source</th><th className="text-right">Amount</th><th className="p-3 text-right">Running</th></tr></thead><tbody>{runningLedger.map((entry) => <tr key={entry.id} className="border-b last:border-0"><td className="p-3">{entry.effective_date}</td><td>{entry.entry_type}</td><td>{entry.note ?? entry.source_type}</td><td className="text-right">{entry.amount_minutes}</td><td className="p-3 text-right font-medium">{entry.running}</td></tr>)}</tbody></table>{ledger.length === 0 && <p className="p-5 text-sm text-neutral-500">No ledger entries for this employee.</p>}</div>
        <div className="rounded-xl border bg-white"><h2 className="border-b px-5 py-3 font-semibold">Job runs</h2>{jobRuns.map((run) => <p key={run.id} className="border-b px-5 py-2 text-xs last:border-0">{run.kind} · {run.source_id} · {run.status} · {run.entries_created} entries</p>)}{jobRuns.length === 0 && <p className="p-5 text-sm text-neutral-500">No jobs have run.</p>}</div>
      </section>}

      {actor?.is_admin && tab === 'demo' && <section className="space-y-4 rounded-xl border bg-white p-5"><div><h2 className="font-semibold">Demo controls</h2><p className="text-xs text-neutral-500">Move the simulated date, then invoke the same retry-safe services production cron would call.</p></div><div className="flex flex-wrap gap-2"><input className={inputClass} type="date" value={demoDate} onChange={(event) => setDemoDate(event.target.value)} /><button className={buttonClass} onClick={() => void setClock()}>Set date</button><button className={buttonClass} onClick={() => void runJob('accruals')}>Run accruals</button><button className={buttonClass} onClick={() => void runJob('rollover')}>Run rollover</button></div>{demoResult && <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{demoResult}</p>}</section>}
    </main>
  )
}
