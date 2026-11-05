import type { ReactNode } from 'react'
import { TextField, type TextFieldProps } from './TextField'

export interface PhoneFieldProps extends Omit<TextFieldProps, 'type' | 'startAddon' | 'leftIcon' | 'label'> {
  label: ReactNode
  /** Fixed country calling code shown before the input. */
  countryCode?: string
}

/**
 * Mobile-number input with a fixed country-code prefix ("+91 | 98765 43210").
 * The prefix is visual; screen readers get it from the label instead ("Mobile Number, +91").
 * Opens the phone keypad on mobile and autofills the national number.
 */
export function PhoneField({ label, countryCode = '+91', ...props }: PhoneFieldProps) {
  return (
    <TextField
      type="tel"
      inputMode="tel"
      autoComplete="tel-national"
      {...props}
      label={
        <>
          {label}
          <span className="sr-only">, country code {countryCode}</span>
        </>
      }
      startAddon={<span aria-hidden>{countryCode}</span>}
    />
  )
}
