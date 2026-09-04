import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('application shell', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      const body = path.endsWith('/employees')
        ? [
            { id: 'adm_lindsey', name: 'Lindsey', is_admin: true },
            { id: 'emp_ada', name: 'Ada', is_admin: false },
          ]
        : path.endsWith('/dev/state')
          ? { today: '2026-03-16' }
          : path.endsWith('/categories')
            ? [{ id: 'cat_vacation', name: 'Vacation', icon: null }]
          : path.endsWith('/policies')
            ? [{
                id: 'pol_vacation', name: 'Vacation', category_id: 'cat_vacation',
                category_name: 'Vacation', created_by: 'adm_lindsey', version_count: 1,
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
              }]
          : path.endsWith('/requests')
            ? [{
                id: 'req_1', employee_id: 'emp_ada', employee_name: 'Ada',
                category_id: 'cat_vacation', reason: 'Trip', status: 'PENDING',
                start_date: '2026-06-01', end_date: '2026-06-02',
                total_minutes: 960, events: [], days: [],
              }]
          : []
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }))
  })

  it('shows the time-off product heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Time-off policies' })).toBeInTheDocument()
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
    const allowNegative = screen.getByLabelText('Allow negative balance')
    const floor = screen.getByLabelText('Negative balance floor minutes')
    expect(floor).toBeDisabled()
    fireEvent.click(allowNegative)
    expect(floor).toBeEnabled()
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
    fireEvent.click(screen.getByRole('button', { name: 'Save new version' }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/policies/pol_vacation',
        expect.objectContaining({ method: 'PUT' }),
      )
    })
  })

  it('exposes preview, partial-day, and cancellation controls to employees', async () => {
    render(<App />)
    await screen.findByRole('button', { name: 'Audit' })
    fireEvent.change(screen.getByLabelText('Acting as'), { target: { value: 'emp_ada' } })
    fireEvent.click(await screen.findByRole('button', { name: 'My requests' }))

    expect(screen.getByLabelText('Partial hours')).toBeInTheDocument()
    expect(screen.getByLabelText('Partial minutes')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Preview request' })).toBeDisabled()
    expect(await screen.findByRole('button', { name: 'Cancel request' })).toBeInTheDocument()
  })
})
