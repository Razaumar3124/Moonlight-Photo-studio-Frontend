import { Bookmark, FolderOpen, Search, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { IconButton } from '@/components/ui/IconButton'
import { formatLength, type LengthUnit } from '@/lib/units'
import { LAYOUT_STYLES } from '../../constants'
import { useSavedDesigns } from '../../hooks/useSavedDesigns'
import { buildScene } from '../../lib/geometry/scene'
import { savedDesignsStore, type SavedDesign } from '../../lib/savedDesigns'
import { WallSvg } from '../WallSvg'

interface SavedDesignsDialogProps {
  open: boolean
  onClose: () => void
  unit: LengthUnit
  onOpenDesign: (design: SavedDesign) => void
  onSaveCurrent: () => void
}

const dateFormat = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

/** "My Saved Templates": search, open or delete saved designs (mock store until Phase 5). */
export function SavedDesignsDialog({
  open,
  onClose,
  unit,
  onOpenDesign,
  onSaveCurrent,
}: SavedDesignsDialogProps) {
  const designs = useSavedDesigns()
  const [query, setQuery] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)
  const emptyRef = useRef<HTMLHeadingElement>(null)

  // The deleted card's buttons vanish with it: put focus somewhere sensible instead of <body>.
  const handleDelete = (id: string) => {
    savedDesignsStore.remove(id)
    requestAnimationFrame(() => (searchRef.current ?? emptyRef.current)?.focus())
  }
  const q = query.trim().toLowerCase()
  const visible = q ? designs.filter((d) => d.title.toLowerCase().includes(q)) : designs

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title="My Saved Templates"
      description={
        designs.length ? `${designs.length} saved ${designs.length === 1 ? 'design' : 'designs'}` : undefined
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
      {designs.length > 0 && (
        <label className="mb-5 flex h-11 max-w-md items-center gap-2 rounded-lg border border-cream-600/60 bg-white px-3 focus-within:border-brand-600 focus-within:ring-3 focus-within:ring-brand-600/15">
          <Search aria-hidden className="size-4 text-ink-500" />
          <span className="sr-only">Search saved designs</span>
          <input
            ref={searchRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name"
            maxLength={80}
            className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-ink-500 sm:text-sm"
          />
        </label>
      )}

      {designs.length === 0 ? (
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
      ) : visible.length === 0 ? (
        <p className="py-10 text-center text-sm text-ink-500">No designs match “{query}”.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((d) => (
            <li key={d.id}>
              <SavedCard
                design={d}
                unit={unit}
                onOpen={() => onOpenDesign(d)}
                onDelete={() => handleDelete(d.id)}
              />
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  )
}

function SavedCard({
  design,
  unit,
  onOpen,
  onDelete,
}: {
  design: SavedDesign
  unit: LengthUnit
  onOpen: () => void
  onDelete: () => void
}) {
  const [confirming, setConfirming] = useState(false)
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
  const scene = useMemo(() => buildScene(design.state), [design.state])
  const style = LAYOUT_STYLES.find((s) => s.id === design.state.layout.style)?.label
  const { widthIn, heightIn } = design.state.wall

  return (
    <article className="flex h-full flex-col overflow-hidden rounded-xl border border-cream-300 bg-white shadow-field transition-[box-shadow,transform] hover:-translate-y-0.5 hover:shadow-card">
      <button
        type="button"
        onClick={onOpen}
        className="block bg-cream-200 p-2"
        aria-label={`Open ${design.title}`}
      >
        <WallSvg scene={scene} detail="low" className="aspect-[4/3] w-full rounded-lg" />
      </button>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <h3 className="truncate font-display text-lg font-semibold text-ink-900" title={design.title}>
          {design.title}
        </h3>
        <p className="text-xs text-ink-500">
          {formatLength(widthIn, unit)} × {formatLength(heightIn, unit)} · {design.state.frames.length} frames
          · {style}
        </p>
        <p className="text-xs text-ink-500">Saved {dateFormat.format(new Date(design.savedAt))}</p>
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
                onClick={() => setConfirming(false)}
              >
                Keep
              </Button>
              <Button size="md" className="h-9 px-3" onClick={onDelete}>
                Delete
              </Button>
            </div>
          ) : (
            <>
              <Button
                size="md"
                className="h-9"
                leftIcon={<FolderOpen aria-hidden className="size-4" />}
                onClick={onOpen}
              >
                Open
              </Button>
              <IconButton
                ref={trashRef}
                label={`Delete ${design.title}`}
                icon={<Trash2 />}
                variant="ghost"
                onClick={() => setConfirming(true)}
              />
            </>
          )}
        </div>
      </div>
    </article>
  )
}
