import { Bookmark, FolderOpen, ImageOff, RefreshCw, Search, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert } from '@/components/feedback/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { IconButton } from '@/components/ui/IconButton'
import { formatLength, type LengthUnit } from '@/lib/units'
import type { DesignListItem } from '@/types/api'
import { LAYOUT_STYLES } from '../../constants'
import { forgetDesignPreview, useDesignPreview } from '../../hooks/useDesignPreview'
import { useDesignList } from '../../hooks/useDesignList'
import { usePhotos } from '../../hooks/usePhotoLibrary'
import { buildScene } from '../../lib/geometry/scene'
import { WallSvg } from '../WallSvg'

interface SavedDesignsDialogProps {
  open: boolean
  onClose: () => void
  unit: LengthUnit
  /** The design being edited, marked "Open now". */
  currentDesignId: string | null
  /** Set while a design is being fetched to open, to show progress on its card. */
  openingId: string | null
  onOpenDesign: (design: DesignListItem) => void
  onSaveCurrent: () => void
  /** A design was deleted from here (the planner may be showing it). */
  onDeleted: (designId: string) => void
}

const dateFormat = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

/** "My Designs": search, open or delete the designs saved to the account (GET/DELETE /designs). */
export function SavedDesignsDialog({
  open,
  onClose,
  unit,
  currentDesignId,
  openingId,
  onOpenDesign,
  onSaveCurrent,
  onDeleted,
}: SavedDesignsDialogProps) {
  const list = useDesignList(open)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const emptyRef = useRef<HTMLHeadingElement>(null)

  // The deleted card's buttons vanish with it: put focus somewhere sensible instead of <body>.
  const handleDelete = async (design: DesignListItem) => {
    setDeleteError(null)
    const result = await list.remove(design.id)
    if (!result.ok) {
      setDeleteError(result.error)
      return
    }
    forgetDesignPreview(design.id)
    onDeleted(design.id)
    requestAnimationFrame(() => (searchRef.current ?? emptyRef.current)?.focus())
  }

  const searching = list.search.trim().length > 0
  const empty = list.status === 'ready' && list.items.length === 0

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title="My Designs"
      description={
        list.status === 'ready' && !searching && list.total
          ? `${list.total} saved ${list.total === 1 ? 'design' : 'designs'}`
          : undefined
      }
      headerActions={
        <Button
          variant="secondary"
          size="md"
          className="h-9"
          leftIcon={<Bookmark aria-hidden className="size-4" />}
          onClick={onSaveCurrent}
        >
          <span className="hidden sm:inline">Save current</span>
          <span className="sm:hidden">Save</span>
        </Button>
      }
    >
      {(list.total > 0 || searching) && (
        <label className="mb-5 flex h-11 max-w-md items-center gap-2 rounded-lg border border-cream-600/60 bg-white px-3 focus-within:border-brand-600 focus-within:ring-3 focus-within:ring-brand-600/15">
          <Search aria-hidden className="size-4 text-ink-500" />
          <span className="sr-only">Search saved designs</span>
          <input
            ref={searchRef}
            type="search"
            value={list.search}
            onChange={(e) => list.setSearch(e.target.value)}
            placeholder="Search by name"
            maxLength={80}
            className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-ink-500 sm:text-sm"
          />
        </label>
      )}

      {deleteError && (
        <Alert tone="error" className="mb-4">
          {deleteError}
        </Alert>
      )}

      {list.status === 'loading' && list.items.length === 0 && (
        <p role="status" className="py-12 text-center text-sm text-ink-500">
          Loading your designs…
        </p>
      )}

      {list.status === 'error' && (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-sm text-ink-700">We couldn’t load your designs.</p>
          <Button
            variant="secondary"
            leftIcon={<RefreshCw aria-hidden className="size-4" />}
            onClick={list.reload}
          >
            Try again
          </Button>
        </div>
      )}

      {empty && !searching && (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <span className="grid size-16 place-items-center rounded-full bg-brand-50 text-brand-600">
            <Bookmark aria-hidden className="size-7" />
          </span>
          <h3 ref={emptyRef} tabIndex={-1} className="font-display text-xl text-ink-900 outline-none">
            No saved designs yet
          </h3>
          <p className="max-w-sm text-sm text-ink-500">Save your current wall to come back to it any time.</p>
          <Button onClick={onSaveCurrent}>Save current design</Button>
        </div>
      )}
      {empty && searching && (
        <p className="py-10 text-center text-sm text-ink-500">No designs match “{list.search.trim()}”.</p>
      )}

      {list.items.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.items.map((d) => (
            <li key={d.id}>
              <SavedCard
                design={d}
                unit={unit}
                current={d.id === currentDesignId}
                opening={d.id === openingId}
                disabled={openingId !== null}
                onOpen={() => onOpenDesign(d)}
                onDelete={() => handleDelete(d)}
              />
            </li>
          ))}
        </ul>
      )}

      {list.hasMore && list.status !== 'error' && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="secondary"
            loading={list.loadingMore}
            loadingText="Loading…"
            onClick={list.loadMore}
          >
            Show more
          </Button>
        </div>
      )}
    </Dialog>
  )
}

function SavedCard({
  design,
  unit,
  current,
  opening,
  disabled,
  onOpen,
  onDelete,
}: {
  design: DesignListItem
  unit: LengthUnit
  current: boolean
  opening: boolean
  disabled: boolean
  onOpen: () => void
  onDelete: () => Promise<void>
}) {
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const keepRef = useRef<HTMLButtonElement>(null)
  const trashRef = useRef<HTMLButtonElement>(null)
  // Swapping trash ⇄ confirm row unmounts the focused button: move focus along with it.
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    ;(confirming ? keepRef : trashRef).current?.focus()
  }, [confirming])

  const library = usePhotos()
  const preview = useDesignPreview(design.id, design.current_version_id)
  const scene = useMemo(
    () => (preview.loaded ? buildScene({ ...preview.loaded.state, photoUrl: library.urlFor }) : null),
    [preview.loaded, library.urlFor],
  )
  const style = preview.loaded
    ? LAYOUT_STYLES.find((s) => s.id === preview.loaded?.state.layout.style)?.label
    : undefined

  return (
    <article className="flex h-full flex-col overflow-hidden rounded-xl border border-cream-300 bg-white shadow-field transition-[box-shadow,transform] hover:-translate-y-0.5 hover:shadow-card">
      <button
        type="button"
        onClick={onOpen}
        disabled={disabled}
        className="block bg-cream-200 p-2 disabled:cursor-progress"
        aria-label={`Open ${design.title}`}
      >
        {scene ? (
          <WallSvg scene={scene} detail="low" className="aspect-[4/3] w-full rounded-lg" />
        ) : (
          <div className="grid aspect-[4/3] w-full place-items-center rounded-lg bg-cream-300/60 text-ink-500">
            {preview.status === 'loading' ? (
              <span role="status" className="text-xs">
                Loading preview…
              </span>
            ) : (
              <span className="flex flex-col items-center gap-1 text-xs">
                <ImageOff aria-hidden className="size-5" />
                {preview.status === 'empty' ? 'No layout saved yet' : 'Preview unavailable'}
              </span>
            )}
          </div>
        )}
      </button>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="truncate font-display text-lg font-semibold text-ink-900" title={design.title}>
            {design.title}
          </h3>
          {current && <Badge tone="brand">Open now</Badge>}
        </div>
        <p className="text-xs text-ink-500">
          {formatLength(design.wall.width_inches, unit)} × {formatLength(design.wall.height_inches, unit)} ·{' '}
          {design.items_count} {design.items_count === 1 ? 'frame' : 'frames'}
          {style ? ` · ${style}` : ''}
        </p>
        <p className="text-xs text-ink-500">
          Saved {dateFormat.format(new Date(design.updated_at))}
          {design.current_version_number ? ` · version ${design.current_version_number}` : ''}
        </p>
        <div className="mt-auto flex items-center justify-between gap-2 pt-3">
          {confirming ? (
            <div
              role="group"
              aria-label={`Delete ${design.title}?`}
              className="flex items-center gap-2 text-sm"
            >
              <span className="font-medium text-danger-600">Delete?</span>
              <Button
                ref={keepRef}
                variant="secondary"
                size="md"
                className="h-9 px-3"
                disabled={deleting}
                onClick={() => setConfirming(false)}
              >
                Keep
              </Button>
              <Button
                size="md"
                className="h-9 px-3"
                loading={deleting}
                loadingText="Deleting…"
                onClick={async () => {
                  setDeleting(true)
                  await onDelete()
                  setDeleting(false)
                  setConfirming(false)
                }}
              >
                Delete
              </Button>
            </div>
          ) : (
            <>
              <Button
                size="md"
                className="h-9"
                leftIcon={<FolderOpen aria-hidden className="size-4" />}
                loading={opening}
                loadingText="Opening…"
                disabled={disabled}
                onClick={onOpen}
              >
                Open
              </Button>
              <IconButton
                ref={trashRef}
                label={`Delete ${design.title}`}
                icon={<Trash2 />}
                variant="ghost"
                disabled={disabled}
                onClick={() => setConfirming(true)}
              />
            </>
          )}
        </div>
      </div>
    </article>
  )
}
