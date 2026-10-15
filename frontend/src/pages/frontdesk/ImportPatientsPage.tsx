import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, Download, FileSpreadsheet } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { Button, Card, ErrorAlert, PageHeader } from '@/components/ui'
import { api, ApiError, downloadFile } from '@/lib/api'
import { formatDate } from '@/lib/format'

interface ImportResult {
  total_rows: number
  valid_rows: number
  rows_with_errors: number
  imported: number
  errors: { row: number; column: string; message: string }[]
  unknown_columns: string[]
  preview: { row: number; name: string; gender: string; date_of_birth: string | null; phone_number: string; mrn: string }[]
}

function useImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ file, dryRun, skipInvalid }: { file: File; dryRun: boolean; skipInvalid: boolean }) => {
      const form = new FormData()
      form.append('file', file)
      form.append('dry_run', String(dryRun))
      form.append('skip_invalid', String(skipInvalid))
      return api<ImportResult>('/api/v1/patients/import/', { method: 'POST', body: form })
    },
    onSuccess: (result) => {
      if (result.imported) void queryClient.invalidateQueries({ queryKey: ['patients'] })
    },
  })
}

function Problems({ result }: { result: ImportResult }) {
  if (!result.errors.length) return null
  return (
    <Card className="mb-6">
      <h3 className="border-b border-slate-100 px-5 py-3 font-medium text-slate-900">
        {result.rows_with_errors} row{result.rows_with_errors === 1 ? '' : 's'} to fix
      </h3>
      <div className="max-h-80 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Row</th>
              <th className="px-4 py-2 font-medium">Column</th>
              <th className="px-4 py-2 font-medium">Problem</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {result.errors.map((error, index) => (
              <tr key={index}>
                <td className="px-4 py-2 tabular-nums">{error.row}</td>
                <td className="px-4 py-2">{error.column}</td>
                <td className="px-4 py-2 text-red-700">{error.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Preview({ result }: { result: ImportResult }) {
  if (!result.preview.length) return null
  return (
    <Card className="mb-6">
      <h3 className="border-b border-slate-100 px-5 py-3 font-medium text-slate-900">
        First {result.preview.length} of {result.valid_rows} ready to import
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Row</th>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Gender</th>
              <th className="px-4 py-2 font-medium">Date of birth</th>
              <th className="px-4 py-2 font-medium">Phone</th>
              <th className="px-4 py-2 font-medium">Record number</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {result.preview.map((row) => (
              <tr key={row.row}>
                <td className="px-4 py-2 tabular-nums">{row.row}</td>
                <td className="px-4 py-2 font-medium text-slate-900">{row.name}</td>
                <td className="px-4 py-2 capitalize">{row.gender || '—'}</td>
                <td className="px-4 py-2">{row.date_of_birth ? formatDate(row.date_of_birth) : '—'}</td>
                <td className="px-4 py-2">{row.phone_number || '—'}</td>
                <td className="px-4 py-2 text-slate-600">{row.mrn}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function ImportPatientsPage() {
  const [file, setFile] = useState<File | null>(null)
  const [skipInvalid, setSkipInvalid] = useState(false)
  const check = useImport()
  const save = useImport()
  const template = useMutation({ mutationFn: () => downloadFile('/api/v1/patients/import-template/') })
  const result = check.data
  const fileError = check.error instanceof ApiError ? check.error.fieldErrors.file : undefined

  function handleCheck(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    save.reset()
    check.mutate({ file, dryRun: true, skipInvalid: false })
  }

  if (save.data?.imported) {
    return (
      <div className="mx-auto max-w-md py-12 text-center">
        <CheckCircle2 className="mx-auto mb-4 size-12 text-emerald-500" aria-hidden />
        <h1 className="text-xl font-semibold text-slate-900">
          {save.data.imported} patient{save.data.imported === 1 ? '' : 's'} imported
        </h1>
        {save.data.total_rows > save.data.imported && (
          <p className="mt-2 text-slate-600">
            {save.data.total_rows - save.data.imported} row(s) with problems were left out. Fix them and import them
            separately.
          </p>
        )}
        <Link to="/patients" className="mt-6 inline-block font-medium text-brand-600 hover:text-brand-700">
          Go to patients
        </Link>
      </div>
    )
  }

  const canImport = result && result.valid_rows > 0 && (result.rows_with_errors === 0 || skipInvalid)

  return (
    <>
      <Link to="/patients" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-brand-700">
        <ArrowLeft className="size-4" aria-hidden /> Patients
      </Link>
      <PageHeader title="Import patients" description="Bring in your existing patient list from Excel or a CSV file." />

      <Card className="mb-6 space-y-4 p-5">
        <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-700">
          <li>
            Download the template, or use your own spreadsheet: the first row must hold column names such as{' '}
            <em>First name</em>, <em>Last name</em> (or <em>Surname</em>), <em>Gender</em>, <em>Date of birth</em>,{' '}
            <em>Phone</em> and <em>Existing record number</em>.
          </li>
          <li>Dates can be written 31/12/1990 or 1990-12-31. Only first and last name are required.</li>
          <li>Upload it below. We'll check every row and show you any problems before anything is saved.</li>
        </ol>
        <Button
          variant="secondary"
          size="sm"
          icon={<Download className="size-4" />}
          loading={template.isPending}
          onClick={() => template.mutate()}
        >
          Download template
        </Button>
        <ErrorAlert error={template.error} />
      </Card>

      <form onSubmit={handleCheck}>
        <Card className="mb-6 flex flex-col gap-4 p-5 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm">
            <span className="mb-1.5 block font-medium text-slate-700">Spreadsheet (.xlsx or .csv, up to 5,000 patients)</span>
            <input
              type="file"
              accept=".csv,.xlsx"
              required
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null)
                check.reset()
                save.reset()
              }}
              className="block w-full text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:font-medium file:text-brand-700 hover:file:bg-brand-100"
            />
            {fileError && <span className="mt-1 block text-red-600">{fileError}</span>}
          </label>
          <Button type="submit" icon={<FileSpreadsheet className="size-4" />} loading={check.isPending} disabled={!file}>
            Check file
          </Button>
        </Card>
      </form>
      {!fileError && <ErrorAlert error={check.error} />}

      {result && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-3">
            <Card className="p-4">
              <p className="text-sm text-slate-500">Rows in the file</p>
              <p className="text-2xl font-semibold tabular-nums text-slate-900">{result.total_rows}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-slate-500">Ready to import</p>
              <p className="text-2xl font-semibold tabular-nums text-emerald-700">{result.valid_rows}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-slate-500">Rows with problems</p>
              <p className="text-2xl font-semibold tabular-nums text-red-700">{result.rows_with_errors}</p>
            </Card>
          </div>
          {result.unknown_columns.length > 0 && (
            <p className="mb-6 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
              These columns weren't recognised and will be ignored: {result.unknown_columns.join(', ')}.
            </p>
          )}
          <Problems result={result} />
          <Preview result={result} />

          <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
            {result.rows_with_errors > 0 ? (
              <label className="flex items-start gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={skipInvalid}
                  onChange={(event) => setSkipInvalid(event.target.checked)}
                  className="mt-0.5 size-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span>Import the {result.valid_rows} good rows now and leave out the rows with problems</span>
              </label>
            ) : (
              <p className="text-sm text-slate-700">Everything looks good.</p>
            )}
            <Button
              disabled={!canImport}
              loading={save.isPending}
              onClick={() => file && save.mutate({ file, dryRun: false, skipInvalid })}
            >
              Import {result.valid_rows} patient{result.valid_rows === 1 ? '' : 's'}
            </Button>
          </Card>
          <div className="mt-4">
            <ErrorAlert error={save.error} />
          </div>
        </>
      )}
    </>
  )
}
