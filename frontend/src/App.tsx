import { useEffect, useState } from 'react'
import { ApiError, api, setActor } from './api/client'
import type { Category, Employee, Policy } from './api/types'

const inputClass = 'rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm'
const buttonClass = 'rounded-lg bg-neutral-900 px-3 py-2 text-sm font-medium text-white'

export default function App() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [policies, setPolicies] = useState<Policy[]>([])
  const [actorId, setActorId] = useState('adm_lindsey')
  const [categoryName, setCategoryName] = useState('')
  const [policyName, setPolicyName] = useState('')
  const [kind, setKind] = useState<'ACCRUAL' | 'UNLIMITED'>('ACCRUAL')
  const [amount, setAmount] = useState('20')
  const [categoryId, setCategoryId] = useState('')
  const [error, setError] = useState('')

  async function load() {
    try {
      const [people, cats, policyRows] = await Promise.all([
        api.get<Employee[]>('/employees'),
        api.get<Category[]>('/categories'),
        api.get<Policy[]>('/policies'),
      ])
      setEmployees(people)
      setCategories(cats)
      setPolicies(policyRows)
      setCategoryId((current) => current || cats[0]?.id || '')
      setError('')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught))
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function createCategory(event: React.FormEvent) {
    event.preventDefault()
    await api.post('/categories', { name: categoryName })
    setCategoryName('')
    await load()
  }

  async function createPolicy(event: React.FormEvent) {
    event.preventDefault()
    const rules = kind === 'UNLIMITED' ? [] : [{
      method: 'TIME', amount, unit: 'DAY', frequency: 'YEARLY', accrues_at: 'START_OF_PERIOD',
    }]
    await api.post('/policies', {
      name: policyName,
      category_id: categoryId,
      effective_from: new Date().toISOString().slice(0, 10),
      kind,
      rules,
      change_reason: 'Policy created',
    })
    setPolicyName('')
    await load()
  }

  async function assign(policyId: string, employeeId: string) {
    await api.post('/policies/' + policyId + '/assignments', {
      employee_ids: [employeeId],
      effective_from: new Date().toISOString().slice(0, 10),
    })
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
              <input className={inputClass + ' w-full'} type="number" min="1" value={amount} onChange={(event) => setAmount(event.target.value)} aria-label="Days per year" />
            )}
            <button className={buttonClass} disabled={!categoryId}>Create policy</button>
          </form>
        </section>
      )}

      <section className="space-y-3">
        {policies.map((policy) => (
          <article key={policy.id} className="rounded-xl border bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold">{policy.name}</h2>
                <p className="text-sm text-neutral-500">
                  {policy.category_name} · {policy.current_version.kind.toLowerCase()} · version {policy.version_count}
                </p>
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
