import { useEffect, useState } from 'react'
import { ApiError, api, setActor } from './api/client'
import type { Balance, Category, Employee, Holiday, Policy, TimeOffRequest } from './api/types'

const inputClass = 'rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm'
const buttonClass = 'rounded-lg bg-neutral-900 px-3 py-2 text-sm font-medium text-white'

export default function App() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [policies, setPolicies] = useState<Policy[]>([])
  const [balances, setBalances] = useState<Balance[]>([])
  const [requests, setRequests] = useState<TimeOffRequest[]>([])
  const [actorId, setActorId] = useState('adm_lindsey')
  const [categoryName, setCategoryName] = useState('')
  const [policyName, setPolicyName] = useState('')
  const [kind, setKind] = useState<'ACCRUAL' | 'UNLIMITED'>('ACCRUAL')
  const [amount, setAmount] = useState('20')
  const [tenureMonths, setTenureMonths] = useState('')
  const [tenureAmount, setTenureAmount] = useState('')
  const [maxBalance, setMaxBalance] = useState('')
  const [carryoverCap, setCarryoverCap] = useState('')
  const [expires, setExpires] = useState(false)
  const [holidays, setHolidays] = useState<Holiday[]>([])
  const [categoryId, setCategoryId] = useState('')
  const [error, setError] = useState('')
  const [requestCategoryId, setRequestCategoryId] = useState('')
  const [requestStart, setRequestStart] = useState('')
  const [requestEnd, setRequestEnd] = useState('')

  async function load() {
    try {
      const year = new Date().getFullYear()
      const [people, cats, policyRows, holidayRows] = await Promise.all([
        api.get<Employee[]>('/employees'),
        api.get<Category[]>('/categories'),
        api.get<Policy[]>('/policies'),
        api.get<Holiday[]>('/holidays?year=' + year),
      ])
      setEmployees(people)
      setCategories(cats)
      setPolicies(policyRows)
      setHolidays(holidayRows)
      setCategoryId((current) => current || cats[0]?.id || '')
      setRequestCategoryId((current) => current || cats[0]?.id || '')
      setError('')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10)
    api.get<Balance[]>('/employees/' + actorId + '/balances?on_date=' + today)
      .then(setBalances)
      .catch(() => setBalances([]))
  }, [actorId])

  useEffect(() => {
    api.get<TimeOffRequest[]>('/requests')
      .then(setRequests)
      .catch(() => setRequests([]))
  }, [actorId])

  async function createCategory(event: React.FormEvent) {
    event.preventDefault()
    await api.post('/categories', { name: categoryName })
    setCategoryName('')
    await load()
  }

  async function createPolicy(event: React.FormEvent) {
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
    await api.post('/policies', {
      name: policyName,
      category_id: categoryId,
      effective_from: new Date().toISOString().slice(0, 10),
      kind,
      rules,
      change_reason: 'Policy created',
      max_balance_minutes: maxBalance ? Number(maxBalance) : null,
      carryover_cap_minutes: carryoverCap ? Number(carryoverCap) : null,
      expires_at_period_end: expires,
      tenure_transition: 'NEXT_PERIOD',
    })
    setPolicyName('')
    await load()
  }

  async function syncHolidays() {
    const year = new Date().getFullYear()
    setHolidays(await api.post<Holiday[]>('/holidays/sync?year=' + year))
  }

  async function assign(policyId: string, employeeId: string) {
    await api.post('/policies/' + policyId + '/assignments', {
      employee_ids: [employeeId],
      effective_from: new Date().toISOString().slice(0, 10),
    })
  }

  async function submitRequest(event: React.FormEvent) {
    event.preventDefault()
    await api.post('/requests', {
      employee_id: actorId,
      category_id: requestCategoryId,
      reason: 'Time off',
      start_date: requestStart,
      end_date: requestEnd,
    })
    setRequests(await api.get<TimeOffRequest[]>('/requests'))
  }

  async function decide(requestId: string, action: 'approve' | 'deny') {
    await api.post('/requests/' + requestId + '/' + action, {})
    setRequests(await api.get<TimeOffRequest[]>('/requests'))
  }

  const actor = employees.find((employee) => employee.id === actorId)

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-neutral-500">Northstar Robotics</p>
          <h1 className="mt-1 text-3xl font-semibold">Time-off policies</h1>
        </div>
        <label className="text-xs text-neutral-600">
          Acting as
          <select
            className={inputClass + ' ml-2'}
            value={actorId}
            onChange={(event) => {
              setActorId(event.target.value)
              setActor(event.target.value)
            }}
          >
            {employees.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.name}{employee.is_admin ? ' (admin)' : ''}
              </option>
            ))}
          </select>
        </label>
      </header>

      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {balances.map((balance) => (
          <article key={balance.category_id} className="rounded-xl border bg-white p-5">
            <p className="text-sm font-medium">{balance.category_name}</p>
            <p className="mt-2 text-2xl font-semibold">
              {!balance.has_policy
                ? 'No policy set'
                : balance.is_unlimited
                  ? 'Unlimited'
                  : (balance.balance_minutes / balance.day_minutes).toFixed(2) + ' days'}
            </p>
            {balance.policy_name && <p className="mt-1 text-xs text-neutral-500">{balance.policy_name}</p>}
          </article>
        ))}
      </section>

      {actor?.is_admin && (
        <section className="grid gap-4 rounded-xl border bg-white p-5 md:grid-cols-2">
          <form onSubmit={createCategory} className="space-y-3">
            <h2 className="font-semibold">Add category</h2>
            <input className={inputClass + ' w-full'} value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="Vacation" required />
            <button className={buttonClass}>Create category</button>
          </form>
          <form onSubmit={createPolicy} className="space-y-3">
            <h2 className="font-semibold">Add policy</h2>
            <input className={inputClass + ' w-full'} value={policyName} onChange={(event) => setPolicyName(event.target.value)} placeholder="Full-time vacation" required />
            <div className="grid grid-cols-2 gap-2">
              <select className={inputClass} value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
                {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
              <select className={inputClass} value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}>
                <option value="ACCRUAL">Accrual</option>
                <option value="UNLIMITED">Unlimited</option>
              </select>
            </div>
            {kind === 'ACCRUAL' && (
              <div className="grid grid-cols-2 gap-2">
                <input className={inputClass} type="number" min="1" value={amount} onChange={(event) => setAmount(event.target.value)} aria-label="Days per year" placeholder="Days per year" />
                <input className={inputClass} type="number" min="1" value={maxBalance} onChange={(event) => setMaxBalance(event.target.value)} aria-label="Maximum balance minutes" placeholder="Max balance minutes" />
                <input className={inputClass} type="number" min="0" value={carryoverCap} onChange={(event) => setCarryoverCap(event.target.value)} aria-label="Carryover cap minutes" placeholder="Carryover cap minutes" disabled={expires} />
                <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={expires} onChange={(event) => setExpires(event.target.checked)} disabled={Boolean(carryoverCap)} /> Expire at year end</label>
                <input className={inputClass} type="number" min="1" value={tenureMonths} onChange={(event) => setTenureMonths(event.target.value)} aria-label="Tenure tier months" placeholder="Tier after months" />
                <input className={inputClass} type="number" min="1" value={tenureAmount} onChange={(event) => setTenureAmount(event.target.value)} aria-label="Tenure tier days" placeholder="Tier days per year" />
              </div>
            )}
            <button className={buttonClass} disabled={!categoryId}>Create policy</button>
          </form>
          <div className="space-y-3 md:col-span-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold">Holiday calendar</h2>
                <p className="text-xs text-neutral-500">Observed dates are frozen into submitted requests.</p>
              </div>
              <button className={buttonClass} type="button" onClick={() => void syncHolidays()}>Sync US holidays</button>
            </div>
            <p className="text-sm text-neutral-600">
              {holidays.length ? `${holidays.length} holidays loaded for ${new Date().getFullYear()}` : 'No holidays loaded.'}
            </p>
          </div>
        </section>
      )}

      {!actor?.is_admin && (
        <form onSubmit={submitRequest} className="grid gap-3 rounded-xl border bg-white p-5 sm:grid-cols-4">
          <select className={inputClass} value={requestCategoryId} onChange={(event) => setRequestCategoryId(event.target.value)}>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <input className={inputClass} type="date" value={requestStart} onChange={(event) => setRequestStart(event.target.value)} required />
          <input className={inputClass} type="date" value={requestEnd} onChange={(event) => setRequestEnd(event.target.value)} required />
          <button className={buttonClass}>Request time off</button>
        </form>
      )}

      <section className="rounded-xl border bg-white">
        <h2 className="border-b px-5 py-4 font-semibold">Requests</h2>
        {requests.map((request) => (
          <div key={request.id} className="flex flex-wrap items-center gap-3 border-b px-5 py-3 text-sm last:border-0">
            <span className="font-medium">{request.employee_name}</span>
            <span className="text-neutral-500">{request.start_date} to {request.end_date}</span>
            <span className="rounded-full bg-neutral-100 px-2 py-1 text-xs">{request.status.toLowerCase()}</span>
            {actor?.is_admin && request.status === 'PENDING' && (
              <span className="ml-auto flex gap-2">
                <button className={buttonClass} onClick={() => void decide(request.id, 'approve')}>Approve</button>
                <button className={inputClass} onClick={() => void decide(request.id, 'deny')}>Deny</button>
              </span>
            )}
          </div>
        ))}
        {requests.length === 0 && <p className="p-5 text-sm text-neutral-500">No requests.</p>}
      </section>

      <section className="space-y-3">
        {policies.map((policy) => (
          <article key={policy.id} className="rounded-xl border bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold">{policy.name}</h2>
                <p className="text-sm text-neutral-500">
                  {policy.category_name} · {policy.current_version.kind.toLowerCase()} · version {policy.version_count}
                </p>
                {policy.current_version.kind === 'ACCRUAL' && (
                  <p className="mt-1 text-xs text-neutral-500">
                    {policy.current_version.rules.length > 1 ? `${policy.current_version.rules.length} tenure tiers · ` : ''}
                    {policy.current_version.max_balance_minutes ? `cap ${policy.current_version.max_balance_minutes} min · ` : ''}
                    {policy.current_version.expires_at_period_end
                      ? 'expires yearly'
                      : policy.current_version.carryover_cap_minutes !== null
                        ? `carryover ${policy.current_version.carryover_cap_minutes} min`
                        : 'no rollover limit'}
                  </p>
                )}
              </div>
              {actor?.is_admin && (
                <select
                  className={inputClass}
                  defaultValue=""
                  onChange={(event) => { if (event.target.value) void assign(policy.id, event.target.value) }}
                  aria-label={'Assign employee to ' + policy.name}
                >
                  <option value="">Assign employee…</option>
                  {employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}
                </select>
              )}
            </div>
          </article>
        ))}
        {policies.length === 0 && (
          <p className="rounded-xl border border-dashed p-8 text-center text-sm text-neutral-500">No policies yet.</p>
        )}
      </section>
    </main>
  )
}
