import { useRef, useState, type DragEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { createSubmission } from '../api/submissions'

interface Props {
  problemSlug: string
  contestId?: number | null
  onSubmitted?: (submissionId: number) => void
}

export function SubmissionUploader({ problemSlug, contestId, onSubmitted }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [filename, setFilename] = useState<string | null>(null)
  const [parsing, setParsing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  async function handleFile(file: File) {
    setFilename(file.name)
    setError(null)
    setParsing(true)
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
        throw new Error(t('uploader.invalidGraph'))
      }
      await submit(parsed)
    } catch (err) {
      setError(extractMessage(err, t('common.unknownError')))
    } finally {
      setParsing(false)
    }
  }

  async function submit(graph: Record<string, unknown>) {
    setSubmitting(true)
    try {
      const submission = await createSubmission({
        problem_slug: problemSlug,
        graph_json: graph,
        contest_id: contestId ?? null,
      })
      onSubmitted?.(submission.id)
      navigate(`/submissions/${submission.id}`)
    } catch (err) {
      setError(extractMessage(err, t('common.unknownError')))
    } finally {
      setSubmitting(false)
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) void handleFile(file)
  }

  return (
    <div
      className={`rounded border border-dashed bg-bg p-6 text-center transition-colors ${
        dragging ? 'border-accent bg-accent/5' : 'border-border'
      }`}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/json,.json"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) void handleFile(f)
        }}
      />
      {parsing || submitting ? (
        <div className="text-sm text-text-muted">
          {parsing ? t('uploader.parsing') : t('uploader.uploading')}
        </div>
      ) : (
        <>
          <div className="text-sm text-text">{t('uploader.dropHere')}</div>
          <div className="mt-1 text-xs text-text-muted">{t('uploader.or')}</div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="btn-primary mt-3"
          >
            {t('uploader.selectFile')}
          </button>
          {filename && (
            <div className="mt-3 font-mono text-xs text-text-muted">
              {t('uploader.lastSelected', { name: filename })}
            </div>
          )}
        </>
      )}
      {error && <div className="mt-3 text-sm text-rose-400">{error}</div>}
    </div>
  )
}

function extractMessage(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: unknown } } }).response
    const detail = resp?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg ?? '').join(', ')
  }
  if (err instanceof Error) return err.message
  return fallback
}
