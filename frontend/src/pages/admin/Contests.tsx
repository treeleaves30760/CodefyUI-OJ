import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  createContest,
  deleteContest,
  listContests,
  type ContestListItem,
  type ContestVisibility,
} from '../../api/contests'
import { extractApiError } from '../../api/error'

export function AdminContests() {
  const { t } = useTranslation()
  const [items, setItems] = useState<ContestListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  async function refresh() {
    try {
      setError(null)
      const data = await listContests()
      setItems(data)
    } catch (err) {
      setError(extractApiError(err, t('common.unknownError')))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function remove(c: ContestListItem) {
    if (!confirm(t('admin.contests.confirmDelete', { slug: c.slug }))) return
    try {
      await deleteContest(c.slug)
      await refresh()
    } catch (err) {
      setError(extractApiError(err, t('common.unknownError')))
    }
  }

  return (
    <div>
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('admin.contests.title')}</h1>
          <p className="mt-1 text-text-muted">{t('admin.contests.subtitle')}</p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="btn-primary">
          {showForm ? t('admin.contests.closeForm') : t('admin.contests.newButton')}
        </button>
      </header>

      {error && (
        <div className="mt-4 rounded border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      {showForm && (
        <ContestForm
          onCreated={async () => {
            setShowForm(false)
            await refresh()
          }}
          onError={setError}
        />
      )}

      <section className="mt-8 overflow-hidden rounded-lg border border-border bg-surface">
        {loading ? (
          <div className="p-6 text-text-muted">{t('common.loading')}</div>
        ) : items.length === 0 ? (
          <div className="p-6 text-text-muted">{t('admin.contests.empty')}</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">{t('admin.contests.colTitle')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.contests.colStatus')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.contests.colProblems')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.contests.colSchedule')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.contests.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium">{c.title}</div>
                    <div className="font-mono text-xs text-text-muted">{c.slug}</div>
                  </td>
                  <td className="px-4 py-3 text-text-muted">{c.runtime_status}</td>
                  <td className="px-4 py-3 tabular-nums">{c.problem_count}</td>
                  <td className="px-4 py-3 text-xs text-text-muted">
                    <div>{new Date(c.start_at).toLocaleString()}</div>
                    <div>→ {new Date(c.end_at).toLocaleString()}</div>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => void remove(c)}
                      className="text-rose-400 hover:text-rose-300"
                    >
                      {t('admin.contests.delete')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

function ContestForm({
  onCreated,
  onError,
}: {
  onCreated: () => Promise<void>
  onError: (msg: string) => void
}) {
  const { t } = useTranslation()
  const [slug, setSlug] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [visibility, setVisibility] = useState<ContestVisibility>('public')
  const [startAt, setStartAt] = useState(toLocalInput(new Date()))
  const [endAt, setEndAt] = useState(toLocalInput(addHours(new Date(), 24)))
  const [problemsCsv, setProblemsCsv] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      const problems = problemsCsv
        .split(',')
        .map((s, i) => {
          const slug = s.trim()
          return slug ? { problem_slug: slug, points: 100, display_order: i } : null
        })
        .filter((x): x is { problem_slug: string; points: number; display_order: number } => x !== null)
      await createContest({
        slug,
        title,
        description_md: description,
        start_at: new Date(startAt).toISOString(),
        end_at: new Date(endAt).toISOString(),
        visibility,
        problems,
      })
      await onCreated()
    } catch (err) {
      onError(extractApiError(err, t('common.unknownError')))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 grid gap-4 rounded-lg border border-border bg-surface p-6 md:grid-cols-2">
      <Field label={t('admin.contests.fieldSlug')}>
        <input required pattern="^[a-z0-9-]+$" className="input" value={slug} onChange={(e) => setSlug(e.target.value)} />
      </Field>
      <Field label={t('admin.contests.fieldTitle')}>
        <input required className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <Field label={t('admin.contests.fieldVisibility')}>
        <select className="input" value={visibility} onChange={(e) => setVisibility(e.target.value as ContestVisibility)}>
          <option value="public">public</option>
          <option value="private">private</option>
          <option value="invite_only">invite_only</option>
        </select>
      </Field>
      <Field label={t('admin.contests.fieldProblems')} hint={t('admin.contests.fieldProblemsHint')}>
        <input className="input" value={problemsCsv} onChange={(e) => setProblemsCsv(e.target.value)} />
      </Field>
      <Field label={t('admin.contests.fieldStart')}>
        <input required type="datetime-local" className="input" value={startAt} onChange={(e) => setStartAt(e.target.value)} />
      </Field>
      <Field label={t('admin.contests.fieldEnd')}>
        <input required type="datetime-local" className="input" value={endAt} onChange={(e) => setEndAt(e.target.value)} />
      </Field>
      <Field label={t('admin.contests.fieldDescription')} className="md:col-span-2">
        <textarea rows={4} className="input font-mono text-xs" value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>
      <div className="md:col-span-2">
        <button type="submit" disabled={submitting} className="btn-primary">
          {submitting ? t('admin.contests.creating') : t('admin.contests.create')}
        </button>
      </div>
    </form>
  )
}

function Field({
  label,
  hint,
  children,
  className = '',
}: {
  label: string
  hint?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <label className={`block ${className}`}>
      <span className="text-sm text-text-muted">{label}</span>
      {hint && <span className="ml-2 text-xs text-text-muted/70">{hint}</span>}
      <div className="mt-1">{children}</div>
    </label>
  )
}

function toLocalInput(d: Date): string {
  const off = d.getTimezoneOffset()
  const local = new Date(d.getTime() - off * 60000)
  return local.toISOString().slice(0, 16)
}

function addHours(d: Date, h: number): Date {
  return new Date(d.getTime() + h * 3600_000)
}
