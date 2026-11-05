import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge class names and resolve Tailwind conflicts so a consumer's className
 * reliably overrides a component's defaults: cn('px-4', 'px-6') -> 'px-6'.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
