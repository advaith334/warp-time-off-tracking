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
