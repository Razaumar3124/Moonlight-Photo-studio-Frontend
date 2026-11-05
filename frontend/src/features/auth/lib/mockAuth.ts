import type { LoginRequest, RegisterRequest } from '@/types/api'

/**
 * TEMPORARY stand-ins for the auth API (UI-only phases).
 * Phase 5 replaces these with `services/auth.ts` calls. The function signatures are the same,
 * so hooks don't change. Nothing here touches the network or stores tokens.
 */

const MOCK_LATENCY_MS = 700

function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'))
    const onAbort = () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

export async function mockLogin(_request: LoginRequest, signal?: AbortSignal): Promise<void> {
  await wait(MOCK_LATENCY_MS, signal)
}

export async function mockRegister(_request: RegisterRequest, signal?: AbortSignal): Promise<void> {
  await wait(MOCK_LATENCY_MS, signal)
}
