import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('application shell', () => {
  it('shows the time-off product heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Employee Time Off' })).toBeInTheDocument()
  })
})
