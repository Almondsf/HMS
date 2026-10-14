/**
 * Small chart pieces for the reports. Every chart here is a single series:
 * one mark colour (brand-600, which clears 3:1 against white; brand-500 does
 * not), no legend (the title names the series), values in text colours.
 */
import { useState, type ReactNode } from 'react'

import { Card, cx } from '@/components/ui'

const MARK = 'bg-brand-600'

/** Compact numbers for tiles: 1,284 / 12.9K / 4.2M */
export function compact(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: value >= 10_000 ? 'compact' : 'standard', maximumFractionDigits: 1 }).format(value)
}

export function StatTile({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return (
    <Card className="p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900 tabular-nums">{value}</p>
      {detail && <p className="mt-1 text-xs text-slate-500">{detail}</p>}
    </Card>
  )
}

/** Ranked horizontal bars with the value at each bar's tip. */
export function BarList({
  title,
  rows,
  format = (value) => compact(value),
  empty = 'No data for this period.',
}: {
  title: string
  rows: { label: ReactNode; value: number; key: string }[]
  format?: (value: number) => string
  empty?: string
}) {
  const max = Math.max(...rows.map((row) => row.value), 0)
  return (
    <Card className="p-5">
      <h3 className="mb-4 font-medium text-slate-900">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">{empty}</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.key} className="grid grid-cols-[minmax(0,10rem)_1fr] items-center gap-3 sm:grid-cols-[minmax(0,14rem)_1fr]">
              <span className="truncate text-sm text-slate-700" title={typeof row.label === 'string' ? row.label : undefined}>
                {row.label}
              </span>
              <span className="flex items-center gap-2">
                {/* Bar grows from the left baseline: square there, 4px rounded at the data end */}
                <span
                  className={cx('h-4 rounded-r-[4px]', MARK)}
                  style={{ width: max ? `max(${(row.value / max) * 80}%, 2px)` : '2px' }}
                  aria-hidden
                />
                <span className="text-sm font-medium text-slate-900 tabular-nums">{format(row.value)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/** Values per day as columns, with a hover tooltip and a table view. */
export function DailyColumns({
  title,
  points,
  format = (value) => compact(value),
}: {
  title: string
  points: { day: string; value: number }[]
  format?: (value: number) => string
}) {
  const [showTable, setShowTable] = useState(false)
  const max = Math.max(...points.map((point) => point.value), 0)
  const label = (day: string) => new Date(`${day}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
  const peak = points.reduce<{ day: string; value: number } | null>((best, point) => (!best || point.value > best.value ? point : best), null)

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h3 className="font-medium text-slate-900">{title}</h3>
        {points.length > 0 && (
          <button type="button" onClick={() => setShowTable(!showTable)} className="text-sm text-brand-600 hover:text-brand-700">
            {showTable ? 'Show chart' : 'Show as table'}
          </button>
        )}
      </div>
      {points.length === 0 ? (
        <p className="text-sm text-slate-500">No data for this period.</p>
      ) : showTable ? (
        <table className="w-full text-sm">
          <tbody className="divide-y divide-slate-100">
            {points.map((point) => (
              <tr key={point.day}>
                <td className="py-1.5 text-slate-600">{label(point.day)}</td>
                <td className="py-1.5 text-right font-medium text-slate-900 tabular-nums">{format(point.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <figure>
          <div className="relative flex h-40 items-end gap-[2px] border-b border-slate-200" role="img" aria-label={`${title}, ${points.length} days; peak ${peak ? `${format(peak.value)} on ${label(peak.day)}` : 'none'}`}>
            {/* Hairline gridline at the peak value */}
            <span className="pointer-events-none absolute inset-x-0 top-0 border-t border-slate-100" aria-hidden />
            {points.map((point) => (
              <div key={point.day} className="group relative flex h-full flex-1 items-end justify-center" tabIndex={0}>
                <span
                  className={cx('w-full max-w-6 rounded-t-[4px] transition-opacity group-hover:opacity-80', MARK)}
                  style={{ height: max ? `max(${(point.value / max) * 100}%, ${point.value ? 2 : 0}px)` : 0 }}
                />
                {/* Tooltip on hover/focus; the hit target is the whole column slot */}
                <span className="pointer-events-none absolute bottom-full mb-1 hidden whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-xs text-white shadow group-hover:block group-focus:block">
                  {label(point.day)}: {format(point.value)}
                </span>
              </div>
            ))}
          </div>
          <figcaption className="mt-2 flex justify-between text-xs text-slate-500">
            <span>{label(points[0].day)}</span>
            {peak && <span>peak {format(peak.value)}</span>}
            <span>{label(points[points.length - 1].day)}</span>
          </figcaption>
        </figure>
      )}
    </Card>
  )
}
