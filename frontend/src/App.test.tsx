import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { setActor } from './api/client'

describe('application shell', () => {
  beforeEach(() => {
    setActor('adm_lindsey')
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const policy = {
        id: 'pol_vacation', name: 'Vacation', category_id: 'cat_vacation',
        category_name: 'Vacation', created_by: 'adm_lindsey', version_count: 1,
        all_employees: true, group_ids: [], group_names: [],
        current_version: {
          id: 'ver_1', version_no: 1, effective_from: '2026-01-01',
          kind: 'ACCRUAL', created_by: 'adm_lindsey', change_reason: 'Initial',
          created_at: '2026-01-01T00:00:00Z', new_hire_proration: 'PRORATE',
          allow_negative: false, negative_floor_minutes: 0,
          max_balance_minutes: null, carryover_cap_minutes: null,
          expires_at_period_end: false, tenure_transition: 'NEXT_PERIOD',
          rules: [{
            id: 'rule_1', method: 'TIME', amount: '20', unit: 'DAY',
            frequency: 'YEARLY', accrues_at: 'START_OF_PERIOD',
            per_minutes_worked: null, min_tenure_months: 0,
          }],
        },
      }
      const body = path.endsWith('/employees')
        ? [
            { id: 'adm_lindsey', name: 'Lindsey', employment_type: 'FULL_TIME', work_minutes_per_day: 480, is_admin: true },
            { id: 'emp_ada', name: 'Ada', employment_type: 'FULL_TIME', work_minutes_per_day: 480, is_admin: false },
          ]
        : path.endsWith('/dev/state')
          ? { today: '2026-03-16' }
          : path.includes('/holidays?year=')
            ? [{ id: 'hol_1', date: '2026-01-01', name: "New Year's Day", observed: false }]
          : path.endsWith('/categories')
            ? [
                { id: 'cat_vacation', name: 'Vacation', icon: null },
                { id: 'cat_sick', name: 'Sick leave', icon: null },
                { id: 'cat_maternity', name: 'Maternity leave', icon: null },
                { id: 'cat_other', name: 'Other', icon: null },
              ]
          : path.endsWith('/groups')
            ? [{
                id: 'grp_full_time', name: 'Full-time employees',
                members: [{ employee_id: 'emp_ada', employee_name: 'Ada', employment_type: 'FULL_TIME' }],
              }, {
                id: 'grp_part_time', name: 'Part-time employees', members: [],
              }]
          : path.endsWith('/policies')
            ? init?.method === 'POST' ? policy : [policy]
          : path.includes('/balances?')
            ? [{
                category_id: 'cat_vacation', category_name: 'Vacation', has_policy: true,
                policy_id: 'pol_vacation', policy_name: 'Vacation', is_unlimited: false,
                balance_minutes: 6240, pending_hold_minutes: 0, available_minutes: 6240,
                day_minutes: 480,
              }]
          : path.endsWith('/requests')
            ? [{
                id: 'req_1', employee_id: 'emp_ada', employee_name: 'Ada',
                category_id: 'cat_vacation', reason: 'Trip', status: 'PENDING',
                start_date: '2026-06-01', end_date: '2026-06-02',
                total_minutes: 960, events: [], days: [
                  { date: '2026-06-01', minutes: 480 },
                  { date: '2026-06-02', minutes: 480 },
                ],
              }]
          : path.endsWith('/requests/preview')
            ? {
                total_minutes: 1080,
                available_minutes: 5400,
                days: [
                  { date: '2026-06-01', minutes: 360 },
                  { date: '2026-06-02', minutes: 360 },
                  { date: '2026-06-03', minutes: 360 },
                ],
              }
          : []
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }))
  })

  it('shows the employee-friendly product heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Time away' })).toBeInTheDocument()
  })

  it('hides admin navigation when acting as an employee', async () => {
    render(<App />)
    await screen.findByRole('button', { name: 'Audit' })
    fireEvent.change(screen.getByLabelText('Acting as'), { target: { value: 'emp_ada' } })
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Audit' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'My requests' })).toBeInTheDocument()
    })
  })

  it('exposes implemented proration and negative-balance policy controls to admins', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Policies' }))

    expect(screen.getByLabelText('New-hire accrual')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Advanced balance rules/ }))
    const allowNegative = screen.getByLabelText('Allow negative balance')
    fireEvent.click(allowNegative)
    expect(screen.getByLabelText('Negative balance floor hours')).toBeEnabled()
  })

  it('loads an existing policy into the future-version editor', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Policies' }))
    fireEvent.click(await screen.findByRole('button', { name: 'New version for Vacation' }))

    expect(screen.getByRole('heading', { name: 'Create future version' })).toBeInTheDocument()
    expect(screen.getByLabelText('Policy name')).toHaveValue('Vacation')
    expect(screen.getByLabelText('Effective from')).toHaveValue('2026-03-16')
    expect(screen.getByLabelText('Change reason')).toBeRequired()
    fireEvent.change(screen.getByLabelText('Change reason'), {
      target: { value: 'Increase allowance' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Schedule new version' }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/policies/pol_vacation',
        expect.objectContaining({ method: 'PUT' }),
      )
    })
  })

  it('configures an hours-worked policy without calendar fields', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Policies' }))
    fireEvent.change(screen.getByLabelText('Policy name'), {
      target: { value: 'Hourly sick leave' },
    })
    fireEvent.change(screen.getByLabelText('Accrual method'), {
      target: { value: 'HOURS_WORKED' },
    })
    fireEvent.change(screen.getByLabelText('Hours earned'), {
      target: { value: '1' },
    })
    fireEvent.change(screen.getByLabelText('Hours worked per accrual'), {
      target: { value: '30' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create policy' }))

    await waitFor(() => {
      const call = vi.mocked(fetch).mock.calls.find(([path, init]) =>
        path === '/api/policies' && init?.method === 'POST')
      expect(call).toBeDefined()
      const body = JSON.parse(String(call?.[1]?.body))
      expect(body.rules[0]).toMatchObject({
        method: 'HOURS_WORKED',
        amount: '1',
        unit: 'HOUR',
        frequency: null,
        accrues_at: null,
        per_minutes_worked: 1800,
      })
    })
  })

  it('exposes preview, partial-day, and cancellation controls to employees', async () => {
    render(<App />)
    await screen.findByRole('button', { name: 'Audit' })
    fireEvent.change(screen.getByLabelText('Acting as'), { target: { value: 'emp_ada' } })
    fireEvent.click(await screen.findByRole('button', { name: 'My requests' }))

    fireEvent.click(screen.getByLabelText('Partial-day request'))
    expect(screen.getByLabelText('Partial hours')).toBeInTheDocument()
    expect(screen.getByLabelText('Partial minutes')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Preview balance impact' })).toBeDisabled()
    expect(await screen.findByRole('button', { name: 'Cancel request' })).toBeInTheDocument()
  })

  it('shows request previews in days and hours instead of raw minutes', async () => {
    render(<App />)
    await screen.findByRole('button', { name: 'Audit' })
    fireEvent.change(screen.getByLabelText('Acting as'), { target: { value: 'emp_ada' } })
    fireEvent.click(await screen.findByRole('button', { name: 'My requests' }))
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2026-06-01' } })
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2026-06-03' } })
    fireEvent.click(screen.getByRole('button', { name: 'Preview balance impact' }))

    expect(await screen.findByText(/2 days 2 hours requested/)).toBeInTheDocument()
    expect(screen.getByText(/11 days 2 hours available/)).toBeInTheDocument()
    expect(screen.queryByText(/1080 minutes/)).not.toBeInTheDocument()
  })

  it('lets an employee describe an other leave type without using another balance', async () => {
    render(<App />)
    await screen.findByRole('button', { name: 'Audit' })
    fireEvent.change(screen.getByLabelText('Acting as'), { target: { value: 'emp_ada' } })
    fireEvent.click(await screen.findByRole('button', { name: 'My requests' }))
    fireEvent.change(screen.getByLabelText('Time-off category'), { target: { value: 'cat_other' } })

    const customType = screen.getByLabelText('Custom time-off type')
    expect(customType).toBeRequired()
    expect(screen.getByRole('button', { name: 'Submit request' })).toBeDisabled()
    fireEvent.change(customType, { target: { value: 'Bereavement leave' } })
    expect(screen.getByText('Your approver will see this label')).toBeInTheDocument()
  })

  it('shows holidays and pending leave on the admin calendar', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Calendar' }))

    expect(screen.getByRole('heading', { name: '2026 calendar' })).toBeInTheDocument()
    expect(screen.getAllByText("New Year's Day").length).toBeGreaterThan(1)
    expect(screen.getAllByTitle('Ada · pending')[0]).toHaveClass('event-pending')
  })

  it('shows employees the plain-language rules behind their balance', async () => {
    render(<App />)
    await screen.findByRole('button', { name: 'Audit' })
    fireEvent.change(screen.getByLabelText('Acting as'), { target: { value: 'emp_ada' } })

    fireEvent.click(await screen.findByText('How this leave works'))
    expect(screen.getByText('20 days added each year')).toBeInTheDocument()
    expect(screen.getByText('• Balance cannot go below zero')).toBeInTheDocument()
  })

  it('lets admins create custom groups and assign their members', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'People groups' }))
    const builder = screen.getByRole('heading', { name: 'Create a group' }).closest('form')!
    fireEvent.change(within(builder).getByLabelText('Group name'), {
      target: { value: 'Seasonal employees' },
    })
    fireEvent.click(within(builder).getByRole('checkbox', { name: /Ada/ }))
    fireEvent.click(within(builder).getByRole('button', { name: 'Create group' }))

    await waitFor(() => {
      const call = vi.mocked(fetch).mock.calls.find(([path, request]) =>
        path === '/api/groups' && request?.method === 'POST')
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({
        name: 'Seasonal employees', employee_ids: ['emp_ada'],
      })
    })
  })

  it('targets a new policy to multiple employee groups', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Policies' }))
    fireEvent.change(screen.getByLabelText('Policy name'), {
      target: { value: 'Flexible vacation' },
    })
    fireEvent.click(screen.getByLabelText('All employees'))
    fireEvent.click(screen.getByText('Full-time employees'))
    fireEvent.click(screen.getByText('Part-time employees'))
    fireEvent.click(screen.getByRole('button', { name: 'Create policy' }))

    await waitFor(() => {
      const call = vi.mocked(fetch).mock.calls.find(([path, request]) =>
        path === '/api/policies' && request?.method === 'POST')
      expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
        all_employees: false,
        group_ids: ['grp_full_time', 'grp_part_time'],
      })
    })
  })
})
