import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useTranslation } from 'react-i18next'
import { downloadTemplate, getProblem, type Problem } from '../api/problems'
import { SubmissionUploader } from '../components/SubmissionUploader'
import { useAuth } from '../auth/AuthContext'
import { useSystem } from '../system/SystemContext'

export function ProblemDetail() {
  const { slug } = useParams<{ slug: string }>()
  const { t } = useTranslation()
  const { user } = useAuth()
  const { status } = useSystem()
  const isPractice = status?.mode === 'practice'
  const canSubmit = isPractice || !!user
  const [problem, setProblem] = useState<Problem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!slug) return
    getProblem(slug)
      .then(setProblem)
      .catch((e) => setError(e.message ?? t('common.loadFailed')))
      .finally(() => setLoading(false))
  }, [slug, t])

  async function handleDownload() {
    if (!slug) return
    const template = await downloadTemplate(slug)
    const blob = new Blob([JSON.stringify(template, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${slug}-template.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return <div className="text-text-muted">{t('common.loading')}</div>
  if (error) return <div className="text-rose-400">{error}</div>
  if (!problem) return <div className="text-text-muted">{t('problems.detail.notFound')}</div>

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <article>
        <div className="mb-2 font-mono text-sm text-text-muted">{problem.slug}</div>
        <h1 className="text-3xl font-bold tracking-tight">{problem.title}</h1>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="rounded border border-border bg-surface px-2 py-0.5 text-text-muted">
            {t('problems.detail.difficultyLabel', {
              value: t(`problems.difficulty.${problem.difficulty}` as const),
            })}
          </span>
          {problem.tags.map((tag) => (
            <span
              key={tag}
              className="rounded border border-border bg-surface px-2 py-0.5 text-text-muted"
            >
              {tag}
            </span>
          ))}
        </div>

        <div className="prose-oj mt-8">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {problem.statement_md || t('problems.detail.noStatement')}
          </ReactMarkdown>
        </div>
      </article>

      <aside className="space-y-6">
        <section className="rounded-lg border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold text-text-muted">{t('problems.detail.prepare')}</h2>
          <button onClick={handleDownload} className="btn-primary mt-3 w-full">
            {t('problems.detail.downloadTemplate')}
          </button>
          <p className="mt-3 text-xs text-text-muted">{t('problems.detail.downloadHint')}</p>
        </section>

        <section className="rounded-lg border border-border bg-surface p-5">
          <h2 className="mb-3 text-sm font-semibold text-text-muted">
            {t('problems.detail.uploadSolution')}
          </h2>
          {!canSubmit ? (
            <div className="rounded border border-dashed border-border bg-bg p-4 text-center text-xs text-text-muted">
              <Link to="/login" className="text-accent hover:underline">
                {t('navbar.login')}
              </Link>
              {' / '}
              <Link to="/register" className="text-accent hover:underline">
                {t('navbar.register')}
              </Link>
            </div>
          ) : problem.has_test_data ? (
            <SubmissionUploader problemSlug={problem.slug} />
          ) : (
            <div className="rounded border border-dashed border-border bg-bg p-4 text-center text-xs text-rose-400">
              {t('problems.detail.noTestData')}
            </div>
          )}
        </section>

        <section className="rounded-lg border border-border bg-surface p-5 text-xs text-text-muted">
          <h2 className="mb-2 text-sm font-semibold text-text">{t('problems.detail.limits')}</h2>
          <div>{t('problems.detail.timeLimit', { seconds: problem.time_limit_seconds })}</div>
          <div>{t('problems.detail.memoryLimit', { mb: problem.memory_limit_mb })}</div>
          <div className="mt-2">
            {t('problems.detail.testDataLabel')}
            {problem.has_test_data ? (
              <span className="text-accent">{t('problems.detail.testDataReady')}</span>
            ) : (
              <span className="text-rose-400">{t('problems.detail.testDataMissing')}</span>
            )}
          </div>
        </section>
      </aside>
    </div>
  )
}
