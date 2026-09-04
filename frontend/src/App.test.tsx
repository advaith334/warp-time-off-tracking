import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('application shell', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      const body = path.endsWith('/employees')
        ? [{ id: 'adm_lindsey', name: 'Lindsey', is_admin: true }]
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
})
