import { CircleCheck, Copy, ExternalLink, MessageCircle } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Alert } from '@/components/feedback/Alert'
import { Spinner } from '@/components/feedback/Spinner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { TextField } from '@/components/ui/TextField'
import { cn } from '@/lib/cn'
import { formatLength, type LengthUnit } from '@/lib/units'
import type { useQuoteRequest } from '../../hooks/useQuoteRequest'
import { whatsAppMessage, whatsAppNumber } from '../../lib/quoteRequest'

type QuoteRequest = ReturnType<typeof useQuoteRequest>

interface QuoteDialogProps {
  quote: QuoteRequest
  /** What is being quoted. */
  design: {
    title: string
    widthIn: number
    heightIn: number
    unit: LengthUnit
    frameCount: number
  }
  /** The design was never saved: it needs a name, and is created first. */
  isNew: boolean
  /** Unsaved changes (or a new design) are saved before the quote is prepared. */
  needsSave: boolean
  contact: { name: string; phone: string | null; email: string }
}

const TITLE_MAX = 80

const WORKING_STEPS: Record<'saving' | 'preview' | 'sending', string> = {
  saving: 'Saving your design…',
  preview: 'Preparing your wall preview…',
  sending: 'Creating your quote request…',
}

const linkButton =
  'inline-flex h-12 w-full items-center justify-center gap-2.5 rounded-field bg-brand-600 px-5 ' +
  'text-base font-semibold text-white shadow-button transition-colors hover:bg-brand-700 ' +
  'active:bg-brand-800'

/**
 * Request a Quote. Confirms what will be sent, saves the design if needed, prepares the quote, and
 * then offers a WhatsApp link for the customer to open and send themselves: nothing is sent
 * automatically, and there is no online price (the studio replies on WhatsApp).
 *
 * "Open WhatsApp" is a real link the customer clicks, so browsers never treat it as a blocked popup.
 */
export function QuoteDialog({ quote, design, isNew, needsSave, contact }: QuoteDialogProps) {
  const { step } = quote
  const working = step === 'saving' || step === 'preview' || step === 'sending'

  return (
    <Dialog
      open={step !== 'closed'}
      onClose={quote.close}
      size="md"
      title="Request a quote"
      description={
        step === 'ready'
          ? 'Review the message in WhatsApp and press Send.'
          : 'Our studio replies on WhatsApp.'
      }
    >
      {step === 'confirm' && (
        <ConfirmStep quote={quote} design={design} isNew={isNew} needsSave={needsSave} contact={contact} />
      )}
      {working && <WorkingStep step={step} />}
      {step === 'ready' && quote.result && <ReadyStep quote={quote} />}
      {step === 'error' && quote.problem && (
        <div className="flex flex-col gap-4">
          <Alert tone="error">{quote.problem.message}</Alert>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={quote.close}>
              Close
            </Button>
            {quote.problem.retryable && <Button onClick={() => void quote.retry()}>Try again</Button>}
          </div>
        </div>
      )}
    </Dialog>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <dt className="text-charcoal-500">{label}</dt>
      <dd className="min-w-0 text-right font-medium break-words text-charcoal-900">{children}</dd>
    </div>
  )
}

function ConfirmStep({ quote, design, isNew, needsSave, contact }: Omit<QuoteDialogProps, never>) {
  const [title, setTitle] = useState(design.title)
  const [error, setError] = useState<string>()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const clean = title.trim().replace(/\s+/g, ' ')
    if (!clean) return setError('Give your design a name.')
    void quote.submit(clean)
  }

  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-4">
      <dl className="divide-y divide-ivory-300 rounded-xl border border-ivory-300 bg-white px-4 py-1.5">
        <Row label="Design">{design.title}</Row>
        <Row label="Wall">
          {formatLength(design.widthIn, design.unit)} × {formatLength(design.heightIn, design.unit)}
        </Row>
        <Row label="Frames">{design.frameCount}</Row>
        <Row label="Customer">
          {contact.name}
          <span className="block text-xs font-normal text-charcoal-500">
            {contact.phone ?? contact.email}
          </span>
        </Row>
      </dl>

      {isNew && (
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
          data-autofocus
          required
        />
      )}

      <Alert tone="info">
        {needsSave
          ? isNew
            ? 'We’ll save this design to My Designs first, so your quote matches it exactly.'
            : 'Your unsaved changes will be saved as a new version first, so your quote matches exactly.'
          : 'Your design is saved. The quote will use that saved design.'}
        <span className="mt-1 block text-xs text-charcoal-500">
          Next you’ll open WhatsApp and press Send. There’s no online price: the studio replies with your
          quotation.
        </span>
      </Alert>

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={quote.close}>
          Cancel
        </Button>
        <Button type="submit" data-autofocus={isNew ? undefined : true}>
          {needsSave ? 'Save and continue' : 'Continue'}
        </Button>
      </div>
    </form>
  )
}

function WorkingStep({ step }: { step: 'saving' | 'preview' | 'sending' }) {
  const order = ['saving', 'preview', 'sending'] as const
  return (
    <div className="flex flex-col items-center gap-5 py-6 text-center" aria-busy="true">
      <Spinner className="size-9" />
      <p role="status" className="text-base font-medium text-charcoal-900">
        {WORKING_STEPS[step]}
      </p>
      <ol className="flex w-full max-w-xs flex-col gap-2 text-left text-sm">
        {order.map((s, i) => {
          const state = order.indexOf(step) > i ? 'done' : s === step ? 'active' : 'todo'
          return (
            <li
              key={s}
              className={cn(
                'flex items-center gap-2',
                state === 'todo' ? 'text-charcoal-400' : 'text-charcoal-700',
              )}
            >
              <span
                aria-hidden
                className={cn(
                  'grid size-5 place-items-center rounded-full text-[0.6875rem] font-semibold',
                  state === 'done'
                    ? 'bg-success-500 text-white'
                    : state === 'active'
                      ? 'bg-brand-600 text-white'
                      : 'bg-ivory-300 text-charcoal-500',
                )}
              >
                {state === 'done' ? '✓' : i + 1}
              </span>
              {WORKING_STEPS[s].replace('…', '')}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function ReadyStep({ quote }: { quote: QuoteRequest }) {
  const result = quote.result
  const [copied, setCopied] = useState<'message' | 'link' | 'failed' | null>(null)
  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(null), 2500)
    return () => window.clearTimeout(timer)
  }, [copied])
  if (!result) return null

  const copy = async (kind: 'message' | 'link') => {
    const text = kind === 'message' ? whatsAppMessage(result.whatsappUrl) : result.reportUrl
    try {
      if (!text) throw new Error('nothing to copy')
      await navigator.clipboard.writeText(text)
      setCopied(kind)
    } catch {
      setCopied('failed')
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col items-center gap-2 text-center">
        <span className="grid size-12 place-items-center rounded-full bg-success-50 text-success-500">
          <CircleCheck aria-hidden className="size-7" />
        </span>
        <h3 className="font-display text-xl text-ink-900">Your quote request is ready</h3>
        <p className="text-sm text-charcoal-500">
          Reference <span className="font-semibold text-charcoal-900">{result.quoteId}</span>
        </p>
      </div>

      <ol className="list-decimal space-y-1 pl-5 text-sm text-charcoal-700">
        <li>Open WhatsApp with your request below.</li>
        <li>Check the message, then press Send.</li>
        <li>We’ll reply with your quotation.</li>
      </ol>

      <a href={result.whatsappUrl} target="_blank" rel="noopener noreferrer" className={linkButton}>
        <MessageCircle aria-hidden className="size-5" />
        Open WhatsApp
      </a>

      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm">
        <a
          href={result.reportUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 font-semibold text-brand-700 underline underline-offset-2"
        >
          <ExternalLink aria-hidden className="size-4" />
          View design report
        </a>
        <button
          type="button"
          onClick={() => void copy('message')}
          className="inline-flex items-center gap-1.5 font-semibold text-brand-700 underline underline-offset-2"
        >
          <Copy aria-hidden className="size-4" />
          Copy message
        </button>
        <button
          type="button"
          onClick={() => void copy('link')}
          className="inline-flex items-center gap-1.5 font-semibold text-brand-700 underline underline-offset-2"
        >
          <Copy aria-hidden className="size-4" />
          Copy report link
        </button>
      </div>
      <p role="status" className="min-h-5 text-center text-xs text-charcoal-500">
        {copied === 'message' && 'Message copied. Paste it into WhatsApp.'}
        {copied === 'link' && 'Report link copied.'}
        {copied === 'failed' && 'Couldn’t copy automatically. Select the text in the report instead.'}
      </p>
      <p className="text-center text-xs text-charcoal-500">
        WhatsApp not opening? Copy the message and send it to the studio
        {whatsAppNumber(result.whatsappUrl) ? ` at ${whatsAppNumber(result.whatsappUrl)}` : ''} yourself.
      </p>
      <div className="flex items-center justify-between gap-2 border-t border-ivory-300 pt-3">
        <button
          type="button"
          onClick={quote.startNew}
          className="text-xs font-semibold text-charcoal-500 underline underline-offset-2"
        >
          Create a new request
        </button>
        <Button variant="secondary" onClick={quote.close}>
          Done
        </Button>
      </div>
    </div>
  )
}
