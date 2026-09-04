/**
 * Thin fetch wrapper.
 *
 * Identity travels in `X-Actor-Id`, set from the user switcher in the top bar.
 * There is no auth in this build (see decision I5 in the README) - but every
 * write the backend performs still records who asked for it.
 */
let actorId = 'adm_lindsey'

export function setActor(id: string) {
  actorId = id
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Actor-Id': actorId,
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      // FastAPI validation errors arrive as a list of {loc, msg}.
      detail = Array.isArray(body.detail)
        ? body.detail.map((d: { msg: string }) => d.msg).join('; ')
        : (body.detail ?? detail)
    } catch {
      /* keep the status text */
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
}
