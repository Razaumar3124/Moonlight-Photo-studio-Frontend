import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { PageLoader } from '@/components/layout/PageLoader'
import { env } from '@/config/env'
import { resolveApiUrl } from '@/services/apiClient'
import NotFoundPage from '@/app/NotFoundPage'

const TOKEN_RE = /^[A-Za-z0-9_-]{16,128}$/

/**
 * `/q/<token>`: the link customers and the studio open from WhatsApp. The branded report itself is
 * rendered by the API (GET /quotes/share/{token}, its own strict CSP, no scripts), so this public
 * route only checks the token's shape and moves the browser there. It works wherever the SPA is
 * hosted, whether or not the host forwards `/q/*` to the API.
 */
export default function SharedReportRedirect() {
  const { token } = useParams()
  const valid = typeof token === 'string' && TOKEN_RE.test(token)

  useEffect(() => {
    if (!valid) return
    window.location.replace(
      resolveApiUrl(`${env.apiBaseUrl}/quotes/share/${encodeURIComponent(token)}`) ?? '/',
    )
  }, [valid, token])

  return valid ? <PageLoader /> : <NotFoundPage />
}
