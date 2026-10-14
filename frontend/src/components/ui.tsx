import { AlertCircle, Loader2 } from 'lucide-react'
import {
  forwardRef,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

// ---- Buttons ----

const BUTTON_VARIANTS = {
  primary: 'bg-brand-500 text-white hover:bg-brand-600 shadow-sm',
  secondary: 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 shadow-sm',
  ghost: 'text-slate-600 hover:bg-brand-50 hover:text-brand-700',
  danger: 'bg-red-600 text-white hover:bg-red-700 shadow-sm',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof BUTTON_VARIANTS
  size?: 'sm' | 'md'
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  className,
  children,
  disabled,
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-60',
        size === 'sm' ? 'px-3 py-1.5 text-sm' : 'px-4 py-2 text-sm',
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  )
}

// ---- Form fields ----

interface FieldProps {
  label: string
  error?: string
  hint?: string
}

function Field({ id, label, error, hint, children }: FieldProps & { id: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-red-600">
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  )
}

const CONTROL =
  'block w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 ' +
  'focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:bg-slate-50'

export const Input = forwardRef<HTMLInputElement, FieldProps & InputHTMLAttributes<HTMLInputElement>>(
  function Input({ label, error, hint, className, ...props }, ref) {
    const id = useId()
    return (
      <Field id={id} label={label} error={error} hint={hint}>
        <input
          ref={ref}
          id={id}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          className={cx(CONTROL, error ? 'border-red-400' : 'border-slate-200', className)}
          {...props}
        />
      </Field>
    )
  },
)

export function Select({
  label,
  error,
  hint,
  className,
  children,
  ...props
}: FieldProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId()
  return (
    <Field id={id} label={label} error={error} hint={hint}>
      <select
        id={id}
        aria-invalid={Boolean(error)}
        className={cx(CONTROL, error ? 'border-red-400' : 'border-slate-200', className)}
        {...props}
      >
        {children}
      </select>
    </Field>
  )
}

export function Textarea({
  label,
  error,
  hint,
  className,
  ...props
}: FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId()
  return (
    <Field id={id} label={label} error={error} hint={hint}>
      <textarea
        id={id}
        rows={3}
        aria-invalid={Boolean(error)}
        className={cx(CONTROL, error ? 'border-red-400' : 'border-slate-200', className)}
        {...props}
      />
    </Field>
  )
}

// ---- Layout & feedback ----

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx('rounded-xl border border-slate-200 bg-white shadow-sm', className)}>{children}</div>
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

const BADGE_TONES = {
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
  gray: 'bg-slate-100 text-slate-700 ring-slate-200',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
}

export function Badge({ tone = 'gray', children }: { tone?: keyof typeof BADGE_TONES; children: ReactNode }) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        BADGE_TONES[tone],
      )}
    >
      {children}
    </span>
  )
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500">
      <Loader2 className="size-5 animate-spin text-brand-500" aria-hidden />
      {label}…
    </div>
  )
}

export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  )
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && <div className="mb-3 rounded-full bg-brand-50 p-3 text-brand-500">{icon}</div>}
      <p className="font-medium text-slate-900">{title}</p>
      {children && <div className="mt-1 text-sm text-slate-500">{children}</div>}
    </div>
  )
}
