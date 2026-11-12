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
  /** The planner is editing a design that already exists: Save adds a new version of it. */
  isExisting: boolean
  saving: boolean
  /** A problem from the last attempt (the dialog stays open so nothing is lost). */
  error: string | null
  onSave: (title: string, asNew: boolean) => void
}

const TITLE_MAX = 80

/** Name-and-save step for "Save Design". */
export function SaveDesignDialog({
  open,
  onClose,
  defaultTitle,
  isExisting,
  saving,
  error,
  onSave,
}: SaveDesignDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={() => {
        if (!saving) onClose()
      }}
      size="sm"
      title="Save design"
      description={
        isExisting ? 'Saves a new version. Earlier versions are kept.' : 'Find it later in My Designs.'
      }
    >
      {/* Keyed form: fresh field each time the dialog opens */}
      <SaveForm
        key={String(open)}
        defaultTitle={defaultTitle}
        isExisting={isExisting}
        saving={saving}
        error={error}
        onSave={onSave}
        onCancel={onClose}
      />
    </Dialog>
  )
}

function SaveForm({
  defaultTitle,
  isExisting,
  saving,
  error: serverError,
  onSave,
  onCancel,
}: {
  defaultTitle: string
  isExisting: boolean
  saving: boolean
  error: string | null
  onSave: (title: string, asNew: boolean) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState(defaultTitle)
  const [asNew, setAsNew] = useState(false)
  const [error, setError] = useState<string>()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (saving) return
    const clean = title.trim().replace(/\s+/g, ' ')
    if (!clean) return setError('Give your design a name.')
    onSave(clean, asNew)
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
        disabled={saving}
      />
      {isExisting && (
        <div className="flex items-start gap-2.5 text-sm text-ink-700">
          <input
            id="save-as-new"
            type="checkbox"
            checked={asNew}
            onChange={(e) => setAsNew(e.target.checked)}
            disabled={saving}
            className="mt-0.5 size-4 accent-brand-600"
          />
          <label htmlFor="save-as-new">
            <span className="font-medium text-ink-900">Save as a new design</span>
            <span className="block text-xs text-ink-500">Keeps the original untouched.</span>
          </label>
        </div>
      )}
      {serverError && <Alert tone="error">{serverError}</Alert>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button
          type="submit"
          loading={saving}
          loadingText="Saving…"
          leftIcon={<Bookmark aria-hidden className="size-4" />}
        >
          {serverError ? 'Try again' : 'Save design'}
        </Button>
      </div>
    </form>
  )
}
