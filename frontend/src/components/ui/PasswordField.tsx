import { Eye, EyeOff, Lock } from 'lucide-react'
import { useId, useState } from 'react'
import { TextField, type TextFieldProps } from './TextField'

export type PasswordFieldProps = Omit<TextFieldProps, 'type' | 'rightSlot'>

/** TextField with a lock icon and a show/hide toggle. */
export function PasswordField({ id, leftIcon = <Lock />, ...props }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false)
  const autoId = useId()
  const inputId = id ?? autoId

  return (
    <TextField
      autoCapitalize="none"
      autoCorrect="off"
      spellCheck={false}
      {...props}
      id={inputId}
      type={visible ? 'text' : 'password'}
      leftIcon={leftIcon}
      rightSlot={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          // A toggle button keeps a constant name; its state is conveyed by aria-pressed.
          aria-label="Show password"
          aria-pressed={visible}
          aria-controls={inputId}
          // Negative margin enlarges the tap target to 40px without shifting the icon.
          className="-mr-2 grid size-10 place-items-center rounded-full text-ink-500 transition-colors hover:bg-cream-200 hover:text-ink-900 [&>svg]:size-5"
        >
          {visible ? <Eye aria-hidden /> : <EyeOff aria-hidden />}
        </button>
      }
    />
  )
}
