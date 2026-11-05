import { PlaceholderPage } from '@/components/layout/PlaceholderPage'
import { TextLink } from '@/components/ui/TextLink'
import { ROUTES } from '@/config/routes'

export default function NotFoundPage() {
  return (
    <PlaceholderPage title="Page not found" subtitle="This frame is empty.">
      <TextLink to={ROUTES.login}>Back to sign in</TextLink>
    </PlaceholderPage>
  )
}
