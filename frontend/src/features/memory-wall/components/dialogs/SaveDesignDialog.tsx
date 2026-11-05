import { Bookmark } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/feedback/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { TextField } from '@/components/ui/TextField'

interface SaveDesignDialogProps {
  open: boolean
  onClose: () => void
  defaultTitle: string
  hasUploads: boolean
  onSave: (title: string) => void
}

const TITLE_MAX = 80

/** Name-and-save step for "Save Design". */
export function SaveDesignDialog({ open, onClose, defaultTitle, hasUploads, onSave }: SaveDesignDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="sm"
      title="Save design"
      description="Find it later in My Saved Templates."
    >
      {/* Keyed form: fresh field each time the dialog opens */}
      <SaveForm
        key={String(open)}
        defaultTitle={defaultTitle}
        hasUploads={hasUploads}
        onSave={onSave}
        onCancel={onClose}
      />
    </Dialog>
  )
}

function SaveForm({
  defaultTitle,
  hasUploads,
  onSave,
  onCancel,
}: {
  defaultTitle: string
  hasUploads: boolean
  onSave: (t: string) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState(defaultTitle)
  const [error, setError] = useState<string>()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const clean = title.trim().replace(/\s+/g, ' ')
    if (!clean) return setError('Give your design a name.')
    onSave(clean)
  }

  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-4">
      <TextField
        label="Design name"
        value={title}
        onChange={(e) => {
          setTitle(e.target.value)
          setError(undefined)
        }}
        error={error}
        maxLength={TITLE_MAX}
        autoComplete="off"
        // Dialog focuses (and selects) this field when it opens.
        data-autofocus
        required
      />
      {hasUploads && (
        <Alert tone="info">
          Uploaded photos are kept for this visit only. Saved copies will show empty frames until photo
          uploads go live.
        </Alert>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" leftIcon={<Bookmark aria-hidden className="size-4" />}>
          Save design
        </Button>
      </div>
    </form>
  )
}
