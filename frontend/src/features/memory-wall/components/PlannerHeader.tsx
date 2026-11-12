import {
  ArrowRight,
  Bookmark,
  ChevronDown,
  FolderHeart,
  LayoutTemplate,
  LogOut,
  MoreHorizontal,
  UserRound,
} from 'lucide-react'
import { Logo } from '@/components/brand/Logo'
import { useToast } from '@/components/feedback/toastContext'
import { Button } from '@/components/ui/Button'
import { Menu } from '@/components/ui/Menu'
import { useAuth } from '@/features/auth/authContext'
import { cn } from '@/lib/cn'
import type { LengthUnit } from '@/lib/units'
import { isApiError } from '@/services/apiClient'
import type { Scene } from '../lib/geometry/scene'
import { FitStatus } from './FitStatus'

interface PlannerHeaderProps {
  title: string
  scene: Scene
  unit: LengthUnit
  sofaOn: boolean
  onGenerate: () => void
  onHideSofa: () => void
  onOpenTemplates: () => void
  onOpenDesigns: () => void
  onSave: () => void
  onQuote: () => void
  /** Phones show Request a Quote in the bottom bar instead. */
  showQuote: boolean
}

/**
 * Studio header: brand · project title + fit status · project actions · profile.
 * Opaque and compact (`--pl-header`); actions collapse into "More" on narrower screens.
 */
export function PlannerHeader({
  title,
  scene,
  unit,
  sofaOn,
  onGenerate,
  onHideSofa,
  onOpenTemplates,
  onOpenDesigns,
  onSave,
  onQuote,
  showQuote,
}: PlannerHeaderProps) {
  return (
    <header className="relative z-30 flex h-(--pl-header) shrink-0 items-center gap-2.5 border-b border-ivory-300 bg-ivory-50 px-3 sm:gap-4 sm:px-4">
      <Logo variant="mark" className="w-6 shrink-0 sm:hidden" />
      <Logo className="hidden w-[6.75rem] shrink-0 sm:block dense:w-24" />
      <span aria-hidden className="hidden h-7 w-px shrink-0 bg-ivory-300 sm:block" />

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="min-w-0">
          <h1 className="truncate font-sans text-[0.625rem] leading-none font-semibold tracking-[0.2em] whitespace-nowrap text-gold-600 uppercase max-lg:sr-only">
            Memory Wall Planner
          </h1>
          <p
            className="truncate font-display text-base leading-tight font-semibold text-charcoal-900 sm:text-lg lg:mt-1"
            title={title}
          >
            {title}
          </p>
        </div>
        <FitStatus
          scene={scene}
          unit={unit}
          sofaOn={sofaOn}
          onGenerate={onGenerate}
          onHideSofa={onHideSofa}
          className="shrink-0"
        />
      </div>

      <nav aria-label="Project" className="flex shrink-0 items-center gap-1.5">
        <div className="hidden items-center gap-0.5 lg:flex">
          <HeaderLink icon={<LayoutTemplate aria-hidden />} onClick={onOpenTemplates}>
            Templates
          </HeaderLink>
          <HeaderLink icon={<FolderHeart aria-hidden />} onClick={onOpenDesigns}>
            My Designs
          </HeaderLink>
        </div>
        <Menu
          label="Project actions"
          iconOnly
          tooltip="bottom"
          className="lg:hidden"
          trigger={<MoreHorizontal aria-hidden className="size-4" />}
          triggerClassName="grid size-8 place-items-center rounded-lg text-charcoal-700 transition-colors hover:bg-ivory-200 aria-expanded:bg-ivory-200"
          sections={[
            {
              id: 'project',
              items: [
                {
                  id: 'templates',
                  icon: <LayoutTemplate />,
                  label: 'All templates',
                  onSelect: onOpenTemplates,
                },
                { id: 'designs', icon: <FolderHeart />, label: 'My Designs', onSelect: onOpenDesigns },
                ...(showQuote
                  ? []
                  : [{ id: 'save', icon: <Bookmark />, label: 'Save design', onSelect: onSave }]),
              ],
            },
          ]}
        />
        <Button
          variant="quiet"
          size="sm"
          leftIcon={<Bookmark aria-hidden />}
          onClick={onSave}
          className={cn(!showQuote && 'hidden', 'max-sm:px-2')}
          aria-label="Save design"
        >
          <span className="max-sm:hidden">Save</span>
        </Button>
        {showQuote && <RequestQuoteButton onClick={onQuote} className="h-8 px-3" />}
        <ProfileMenu onOpenDesigns={onOpenDesigns} />
      </nav>
    </header>
  )
}

function HeaderLink({
  icon,
  onClick,
  children,
}: {
  icon: React.ReactNode
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[0.8125rem] font-medium text-charcoal-700 transition-colors hover:bg-ivory-200 hover:text-charcoal-900 [&>svg]:size-4 [&>svg]:text-charcoal-500"
    >
      {icon}
      {children}
    </button>
  )
}

/** Charcoal "Request a Quote" (the conversion action; crimson stays with Generate Layout). */
export function RequestQuoteButton({
  onClick,
  className,
  short = false,
}: {
  onClick: () => void
  className?: string
  /** Visible label "Quote" (phone bottom bar); the accessible name stays "Request a quote". */
  short?: boolean
}) {
  return (
    <Button
      variant="dark"
      size="sm"
      onClick={onClick}
      className={cn('group', className)}
      aria-label="Request a quote"
    >
      <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
        {short ? (
          'Quote'
        ) : (
          <>
            <span className="max-md:hidden">Request a Quote</span>
            <span className="md:hidden">Quote</span>
          </>
        )}
        <ArrowRight
          aria-hidden
          className="size-4 text-champagne-300 transition-transform duration-200 group-hover:translate-x-0.5"
        />
      </span>
    </Button>
  )
}

/** Avatar menu: My Designs and Sign out. */
function ProfileMenu({ onOpenDesigns }: { onOpenDesigns: () => void }) {
  const { user, logout } = useAuth()
  const toast = useToast()
  return (
    <Menu
      label="Profile"
      iconOnly
      trigger={
        <>
          <span className="grid size-7 place-items-center rounded-full bg-charcoal-800 text-ivory-50">
            <UserRound aria-hidden className="size-4" />
          </span>
          <ChevronDown
            aria-hidden
            className="size-3.5 text-charcoal-500 transition-transform group-aria-expanded/ib:rotate-180 max-sm:hidden"
          />
        </>
      }
      triggerClassName="flex items-center gap-1 rounded-full p-0.5 transition-colors hover:bg-ivory-200 aria-expanded:bg-ivory-200 sm:pr-1.5"
      header={
        <p className="px-2.5 pt-1.5 pb-2 text-xs text-charcoal-500">
          Signed in as{' '}
          <span className="block truncate font-medium text-charcoal-700" title={user?.email}>
            {user?.full_name ?? user?.email ?? 'your account'}
          </span>
        </p>
      }
      sections={[
        {
          id: 'account',
          items: [
            { id: 'designs', icon: <FolderHeart />, label: 'My Designs', onSelect: onOpenDesigns },
            {
              id: 'signout',
              icon: <LogOut />,
              label: 'Sign out',
              // On success the route guard moves to the sign-in page; on failure the session
              // is still live on the server, so say so instead of pretending to sign out.
              onSelect: () => {
                logout().catch((error: unknown) =>
                  toast({
                    tone: 'error',
                    message: isApiError(error)
                      ? 'We couldn’t sign you out. Check your connection and try again.'
                      : 'Something went wrong signing you out. Please try again.',
                  }),
                )
              },
            },
          ],
        },
      ]}
    />
  )
}
