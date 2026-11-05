/**
 * Input limits shared by every auth form (and mirrored server-side, API_ALIGNMENT Q18).
 * One source so login and register can never drift apart.
 */
export const AUTH_LIMITS = {
  /** RFC 5321 maximum address length; also caps the login "mobile or email" field. */
  email: 254,
  fullNameMin: 2,
  fullName: 100,
  /** Room for formatted input such as "+91 (98765) 43210" (17) with slack. */
  phone: 20,
  passwordMin: 8,
  /** Generous ceiling that still guards against megabyte-sized payloads. */
  password: 128,
} as const
