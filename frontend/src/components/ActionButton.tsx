import type { ButtonHTMLAttributes, ReactNode } from 'react'

type ActionButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: ReactNode
  label?: string
  size?: 'sm' | 'md'
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
}

export function ActionButton({
  className = '',
  icon,
  label,
  size = 'sm',
  variant = 'secondary',
  ...props
}: ActionButtonProps) {
  const baseClassName =
    'inline-flex items-center justify-center gap-2 rounded-full border font-medium transition disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400'

  const sizeClassName =
    size === 'md' ? 'px-4 py-2.5 text-sm' : 'px-3 py-2 text-xs'

  const variantClassName =
    variant === 'primary'
      ? 'border-slate-950 bg-slate-950 text-white hover:bg-slate-800 hover:border-slate-800'
      : variant === 'danger'
        ? 'border-rose-200 bg-rose-50 text-rose-700 hover:border-rose-300 hover:bg-rose-100'
        : variant === 'ghost'
          ? 'border-transparent bg-transparent text-slate-600 hover:border-slate-200 hover:bg-white'
          : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50'

  return (
    <button
      className={`${baseClassName} ${sizeClassName} ${variantClassName} ${className}`.trim()}
      {...props}
    >
      {icon ? <span className="-ml-0.5 [&>svg]:size-4">{icon}</span> : null}
      {label ? <span>{label}</span> : null}
    </button>
  )
}
