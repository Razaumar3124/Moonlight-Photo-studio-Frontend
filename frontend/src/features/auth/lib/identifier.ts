/**
 * The login field accepts "Mobile No. or Email". This decides which one the user typed and
 * normalises it for the API: emails are trimmed and lower-cased, Indian mobiles become E.164.
 *
 * Assumption (API_ALIGNMENT Q15 is open): Indian numbers by default. A number typed with a
 * leading "+" is accepted as-is if it looks like valid E.164.
 */

export type ParsedIdentifier =
  { kind: 'email'; value: string } | { kind: 'phone'; value: string } | { kind: 'invalid' }

/**
 * Practical address check (not full RFC 5322): dot-separated local-part atoms (no leading,
 * trailing or double dots), hostname labels that don't start/end with "-", and an alphabetic
 * TLD. Rejects markup and quotes outright. Internationalised (non-ASCII) addresses are not
 * accepted. The server remains the authority.
 */
const EMAIL_RE =
  /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$/
const EMAIL_LOCAL_MAX = 64
const INDIAN_MOBILE_RE = /^[6-9]\d{9}$/
const E164_RE = /^\+[1-9]\d{7,14}$/

export const DEFAULT_COUNTRY_CODE = '+91'

export function isEmail(value: string): boolean {
  const email = value.trim()
  const at = email.lastIndexOf('@')
  return at > 0 && at <= EMAIL_LOCAL_MAX && EMAIL_RE.test(email)
}

/** Returns an E.164 number, or null if the input isn't a recognisable mobile number. */
export function normalizePhone(raw: string, countryCode = DEFAULT_COUNTRY_CODE): string | null {
  const compact = raw.trim().replace(/[\s\-().]/g, '')
  if (compact.startsWith('+')) return E164_RE.test(compact) ? compact : null

  const digits = compact.replace(/^0+/, '') // trunk prefix: 09876543210
  if (INDIAN_MOBILE_RE.test(digits)) return `${countryCode}${digits}`
  // Country code typed without "+": 919876543210
  if (digits.length === 12 && digits.startsWith('91') && INDIAN_MOBILE_RE.test(digits.slice(2))) {
    return `+${digits}`
  }
  return null
}

/**
 * For fields with a fixed "+91" prefix: accepts 98765 43210, 09876543210, 919876543210 or
 * +91 98765 43210 and returns +919876543210. Anything non-Indian returns null.
 */
export function normalizeIndianMobile(raw: string): string | null {
  const phone = normalizePhone(raw, DEFAULT_COUNTRY_CODE)
  return phone?.startsWith(DEFAULT_COUNTRY_CODE) ? phone : null
}

export function parseIdentifier(raw: string): ParsedIdentifier {
  const value = raw.trim()
  if (value.includes('@')) {
    return isEmail(value) ? { kind: 'email', value: value.toLowerCase() } : { kind: 'invalid' }
  }
  const phone = normalizePhone(value)
  return phone ? { kind: 'phone', value: phone } : { kind: 'invalid' }
}
