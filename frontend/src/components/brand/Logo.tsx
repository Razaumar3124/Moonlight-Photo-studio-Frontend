import { brandAssets } from '@/assets/brand'
import { cn } from '@/lib/cn'

interface LogoProps {
  /** Set the width with classes (e.g. `w-48`); height follows the aspect ratio. */
  className?: string
}

/**
 * Horizontal logo lockup. The source SVG is traced (ASSETS.md W1), so keep it ≤ ~260px wide
 * until the vector logo arrives.
 */
export function Logo({ className }: LogoProps) {
  const { src, width, height, alt } = brandAssets.logo
  return (
    <img
      src={src}
      width={width}
      height={height}
      alt={alt}
      decoding="async"
      draggable={false}
      className={cn('h-auto w-48 select-none', className)}
    />
  )
}
