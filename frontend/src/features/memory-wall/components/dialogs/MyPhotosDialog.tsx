import { ImageOff, RefreshCw, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Alert } from '@/components/feedback/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { IconButton } from '@/components/ui/IconButton'
import { cn } from '@/lib/cn'
import { usePhotos } from '../../hooks/usePhotoLibrary'
import type { LibraryPhoto } from '../../lib/photos'

interface MyPhotosDialogProps {
  open: boolean
  onClose: () => void
  /** The photo the frame already shows (marked as current). */
  currentPhotoId: string | null
  onChoose: (photo: LibraryPhoto) => void
  /** After a photo was deleted for good, so frames showing it can let go. */
  onDeleted: (photoId: string) => void
}

/** "My photos": everything the user has uploaded. Pick one for the frame, or delete it. */
export function MyPhotosDialog({ open, onClose, currentPhotoId, onChoose, onDeleted }: MyPhotosDialogProps) {
  const library = usePhotos()
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [message, setMessage] = useState<{ tone: 'error' | 'info'; text: string } | null>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)

  const handleDelete = async (photo: LibraryPhoto) => {
    setDeletingId(photo.id)
    setMessage(null)
    const result = await library.remove(photo.id)
    setDeletingId(null)
    setConfirmId(null)
    if (result.ok) {
      onDeleted(photo.id)
      requestAnimationFrame(() => headingRef.current?.focus())
    } else {
      // "In use" is guidance, not a failure: the photo is safe.
      setMessage({ tone: result.inUse ? 'info' : 'error', text: result.error })
    }
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        setConfirmId(null)
        setMessage(null)
        onClose()
      }}
      size="lg"
      title="My photos"
      description={
        library.status === 'ready' && library.photos.length
          ? `${library.photos.length} ${library.photos.length === 1 ? 'photo' : 'photos'} in your library`
          : 'Photos you’ve uploaded.'
      }
    >
      <h3 ref={headingRef} tabIndex={-1} className="sr-only outline-none">
        Your photos
      </h3>
      {message && (
        <Alert tone={message.tone} className="mb-4">
          {message.text}
        </Alert>
      )}

      {library.status === 'loading' && library.photos.length === 0 && (
        <p role="status" className="py-10 text-center text-sm text-ink-500">
          Loading your photos…
        </p>
      )}

      {library.status === 'error' && library.photos.length === 0 && (
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <p className="text-sm text-ink-700">We couldn’t load your photos.</p>
          <Button
            variant="secondary"
            leftIcon={<RefreshCw aria-hidden className="size-4" />}
            onClick={() => void library.refresh()}
          >
            Try again
          </Button>
        </div>
      )}

      {library.status === 'ready' && library.photos.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <span className="grid size-14 place-items-center rounded-full bg-brand-50 text-brand-600">
            <ImageOff aria-hidden className="size-6" />
          </span>
          <p className="font-display text-lg text-ink-900">No photos yet</p>
          <p className="max-w-sm text-sm text-ink-500">
            Upload a photo for any frame and it will appear here to reuse in other frames and designs.
          </p>
        </div>
      )}

      {library.photos.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {library.photos.map((photo) => {
            const current = photo.id === currentPhotoId
            const confirming = confirmId === photo.id
            return (
              <li
                key={photo.id}
                className={cn(
                  'flex flex-col overflow-hidden rounded-xl border bg-white shadow-field',
                  current ? 'border-brand-600 ring-2 ring-brand-600/20' : 'border-cream-300',
                )}
              >
                <button
                  type="button"
                  onClick={() => onChoose(photo)}
                  aria-label={`Use ${photo.name}${current ? ' (current photo)' : ''}`}
                  className="block aspect-square bg-cream-200"
                >
                  <img
                    src={photo.thumbnailUrl}
                    alt=""
                    loading="lazy"
                    onError={library.reportBroken}
                    className="size-full object-cover"
                  />
                </button>
                <div className="flex flex-col gap-1 p-2">
                  <p className="truncate text-xs font-medium text-ink-900" title={photo.name}>
                    {photo.name}
                  </p>
                  <p className="text-[0.6875rem] text-ink-500">
                    {photo.widthPx} × {photo.heightPx} px
                  </p>
                  {confirming ? (
                    <div
                      role="group"
                      aria-label={`Delete ${photo.name}?`}
                      className="flex items-center gap-1.5"
                    >
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setConfirmId(null)}
                        disabled={deletingId === photo.id}
                      >
                        Keep
                      </Button>
                      <Button
                        size="sm"
                        loading={deletingId === photo.id}
                        loadingText="Deleting…"
                        onClick={() => void handleDelete(photo)}
                      >
                        Delete
                      </Button>
                    </div>
                  ) : (
                    <IconButton
                      label={`Delete ${photo.name}`}
                      icon={<Trash2 />}
                      variant="ghost"
                      className="self-end"
                      onClick={() => {
                        setMessage(null)
                        setConfirmId(photo.id)
                      }}
                    />
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Dialog>
  )
}
