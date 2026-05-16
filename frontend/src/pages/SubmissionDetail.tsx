import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getSubmission, type SubmissionDetail, type SubmissionStatus } from '../api/submissions'

const STATUS_COLOR: Record<SubmissionStatus, string> = {
  queued: 'text-amber-400',
  judging: 'text-sky-400',
  judged: 'text-emerald-400',
  invalid: 'text-rose-400',
  runtime_error: 'text-rose-400',
  timeout: 'text-rose-400',
  error: 'text-rose-400',
}

const TERMINAL: Set<SubmissionStatus> = new Set([
  'judged',
  'invalid',
  'runtime_error',
  'timeout',
  'error',
])

export function SubmissionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const [submission, setSubmission] = useState<SubmissionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollHandle = useRef<number | null>(null)

  useEffect(() => {
    if (!id) return
    const submissionId = Number(id)

    async function load() {
      try {
        const s = await getSubmission(submissionId)
        setSubmission(s)
        if (!TERMINAL.has(s.status)) {
          pollHandle.current = window.setTimeout(load, 2000)
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : t('common.loadFailed'))
      }
    }

    void load()
    return () => {
      if (pollHandle.current !== null) window.clearTimeout(pollHandle.current)
    }
  }, [id, t])

  if (error) return <div className="text-rose-400">{error}</div>
  if (!submission) return <div className="text-text-muted">{t('common.loading')}</div>

  return (
    <div>
      <div className="text-sm text-text-muted">
        <Link to="/submissions" className="hover:text-accent">
          {t('submissions.detail.back')}
        </Link>
      </div>
      <h1 className="mt-3 text-3xl font-bold tracking-tight">
        {t('submissions.detail.title')} <span className="font-mono">#{submission.id}</span>
      </h1>

      <div className="mt-6 grid gap-4 sm:grid-cols-4">
        <Stat label={t('submissions.detail.labelStatus')}>
          <span className={STATUS_COLOR[submission.status]}>
            {t(`submissions.status.${submission.status}` as const)}
          </span>
        </Stat>
        <Stat label={t('submissions.detail.labelScore')}>
          <span className="font-mono">
            {submission.score !== null ? submission.score.toFixed(2) : '—'}
          </span>
        </Stat>
        <Stat label={t('submissions.detail.labelRuntime')}>
          <span className="font-mono">
            {submission.runtime_ms !== null ? `${submission.runtime_ms} ms` : '—'}
          </span>
        </Stat>
        <Stat label={t('submissions.detail.labelSubmittedAt')}>
          <span className="text-xs text-text-muted">
            {new Date(submission.submitted_at).toLocaleString()}
          </span>
        </Stat>
      </div>

      <section className="mt-8 rounded-lg border border-border bg-surface">
        <div className="border-b border-border px-5 py-3 text-sm font-semibold">
          {t('submissions.detail.judgeLog')}
        </div>
        <pre className="overflow-x-auto p-5 font-mono text-xs leading-relaxed text-text">
{submission.judge_log || t('submissions.detail.noLog')}
        </pre>
      </section>

      {submission.raw_result && (
        <section className="mt-6 rounded-lg border border-border bg-surface">
          <div className="border-b border-border px-5 py-3 text-sm font-semibold">
            {t('submissions.detail.rawResult')}
          </div>
          <pre className="overflow-x-auto p-5 font-mono text-xs text-text-muted">
{JSON.stringify(submission.raw_result, null, 2)}
          </pre>
        </section>
      )}
    </div>
  )
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-xs text-text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold tracking-tight">{children}</div>
    </div>
  )
}
