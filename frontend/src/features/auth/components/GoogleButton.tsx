import { iconAssets } from '@/assets/brand'
import { Button, type ButtonProps } from '@/components/ui/Button'

type GoogleButtonProps = Omit<ButtonProps, 'variant' | 'leftIcon' | 'children'> & {
  children?: ButtonProps['children']
}

/** "Continue with Google". Follows Google's guidance: white surface, official four-colour "G". */
export function GoogleButton({ children = 'Continue with Google', ...props }: GoogleButtonProps) {
  const g = iconAssets.google
  return (
    <Button
      variant="secondary"
      size="lg"
      fullWidth
      leftIcon={<img src={g.src} width={20} height={20} alt="" aria-hidden className="size-5" />}
      {...props}
    >
      {children}
    </Button>
  )
}
