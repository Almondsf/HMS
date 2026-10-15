import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'

import { ErrorAlert, Spinner } from '@/components/ui'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/format'

interface LegalDocument {
  kind: 'terms' | 'privacy'
  title: string
  version: string
  is_draft: boolean
  published_at: string
  body: string
}

/** "**bold**" inside a line; everything else is plain text (no HTML is ever injected). */
function inline(text: string): ReactNode[] {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .map((part, index) =>
      part.startsWith('**') && part.endsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong> : part,
    )
}

/** The documents' simple format: "# " heading, "## " subheading, "- " list item, blank line between paragraphs. */
function render(body: string): ReactNode[] {
  const blocks: ReactNode[] = []
  let list: string[] = []
  const flushList = () => {
    if (list.length) {
      blocks.push(
        <ul key={blocks.length} className="my-3 list-disc space-y-1.5 pl-6">
          {list.map((item, index) => (
            <li key={index}>{inline(item)}</li>
          ))}
        </ul>,
      )
      list = []
    }
  }
  for (const line of body.split('\n').map((raw) => raw.trim())) {
    if (line.startsWith('- ')) {
      list.push(line.slice(2))
      continue
    }
    flushList()
    if (!line) continue
    if (line.startsWith('## ')) {
      blocks.push(
        <h2 key={blocks.length} className="mb-2 mt-8 text-lg font-semibold text-slate-900">
          {line.slice(3)}
        </h2>,
      )
    } else if (line.startsWith('# ')) {
      blocks.push(
        <h1 key={blocks.length} className="mb-4 text-3xl font-semibold text-slate-900">
          {line.slice(2)}
        </h1>,
      )
    } else {
      blocks.push(
        <p key={blocks.length} className="my-3">
          {inline(line)}
        </p>,
      )
    }
  }
  flushList()
  return blocks
}

export function LegalPage({ kind }: { kind: LegalDocument['kind'] }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['legal', kind],
    queryFn: () => api<LegalDocument>(`/api/v1/legal/${kind}/`, { anonymous: true }),
    staleTime: Infinity,
  })
  if (isLoading) return <Spinner />
  if (!data) return <ErrorAlert error={error} />

  return (
    <article className="mx-auto max-w-3xl px-4 py-12 leading-relaxed text-slate-700 sm:px-6">
      {data.is_draft && (
        <div
          role="note"
          className="mb-8 flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          This is a draft under legal review and may change before it is final.
        </div>
      )}
      {render(data.body)}
      <p className="mt-10 border-t border-slate-100 pt-4 text-sm text-slate-500">
        Version {data.version} · published {formatDate(data.published_at)}
      </p>
    </article>
  )
}
