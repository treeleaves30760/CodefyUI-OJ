import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  createProblem,
  deleteProblem,
  listProblems,
  updateProblem,
  uploadTestData,
  type ProblemDifficulty,
  type ProblemListItem,
} from '../../api/problems'
import { extractApiError } from '../../api/error'

const DEFAULT_TEMPLATE = JSON.stringify(
  {
    name: 'Starter template',
    description: 'Fill in your solution between __INPUT__ and __SUBMIT__',
    nodes: [
      {
        id: '__INPUT__',
        type: 'CSVReader',
        position: { x: 0, y: 0 },
        data: { params: { path: 'train.csv' } },
      },
      {
        id: '__SUBMIT__',
        type: 'Print',
        position: { x: 300, y: 0 },
        data: { params: {} },
      },
    ],
    edges: [],
  },
  null,
  2,
)

const DEFAULT_JUDGE_SPEC = JSON.stringify(
  {
    required_node_ids: ['__INPUT__', '__SUBMIT__'],
    input_patches: [
      {
        node_id: '__INPUT__',
        param_overrides: { path: '{hidden_test_data}/X_test.csv' },
      },
    ],
    output_reads: [
      { node_id: '__SUBMIT__', port: 'value', save_as: 'y_pred' },
    ],
    scoring: {
      method: 'accuracy',
      target_output: 'y_pred',
      ground_truth: '{hidden_test_data}/y_test.csv',
      threshold: 0.85,
      full_score: 100,
    },
    time_limit_seconds: 60,
    memory_limit_mb: 2048,
  },
  null,
  2,
)

export function AdminProblems() {
  const { t } = useTranslation()
  const [items, setItems] = useState<ProblemListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  async function refresh() {
    try {
      setError(null)
      const data = await listProblems(false)
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

  async function togglePublish(p: ProblemListItem) {
    try {
      await updateProblem(p.slug, { published: !p.published })
      await refresh()
    } catch (err) {
      setError(extractApiError(err, t('common.unknownError')))
    }
  }

  async function remove(p: ProblemListItem) {
    if (!confirm(t('admin.problems.confirmDelete', { slug: p.slug }))) return
    try {
      await deleteProblem(p.slug)
      await refresh()
    } catch (err) {
      setError(extractApiError(err, t('common.unknownError')))
    }
  }

  async function uploadFile(p: ProblemListItem, file: File) {
    try {
      await uploadTestData(p.slug, file)
      await refresh()
    } catch (err) {
      setError(extractApiError(err, t('common.unknownError')))
    }
  }

  return (
    <div>
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('admin.problems.title')}</h1>
          <p className="mt-1 text-text-muted">{t('admin.problems.subtitle')}</p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="btn-primary">
          {showForm ? t('admin.problems.closeForm') : t('admin.problems.newButton')}
        </button>
      </header>

      {error && <div className="mt-4 rounded border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">{error}</div>}

      {showForm && (
        <ProblemForm
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
          <div className="p-6 text-text-muted">{t('admin.problems.empty')}</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">{t('admin.problems.colTitle')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.problems.colDifficulty')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.problems.colPublished')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.problems.colTestData')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.problems.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium">{p.title}</div>
                    <div className="font-mono text-xs text-text-muted">{p.slug}</div>
                  </td>
                  <td className="px-4 py-3 text-text-muted">{p.difficulty}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => void togglePublish(p)}
                      className={`rounded border px-2 py-1 text-xs ${
                        p.published
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                          : 'border-border text-text-muted hover:border-accent hover:text-accent'
                      }`}
                    >
                      {p.published ? t('admin.problems.published') : t('admin.problems.draft')}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    {p.has_test_data ? (
                      <span className="text-emerald-300">✓ {t('admin.problems.testDataReady')}</span>
                    ) : (
                      <label className="cursor-pointer text-accent hover:underline">
                        {t('admin.problems.uploadTestData')}
                        <input
                          type="file"
                          accept=".zip,.tar.gz,.tgz"
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0]
                            if (file) void uploadFile(p, file)
                          }}
                        />
                      </label>
                    )}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    <button
                      onClick={() => void remove(p)}
                      className="text-rose-400 hover:text-rose-300"
                    >
                      {t('admin.problems.delete')}
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

function ProblemForm({
  onCreated,
  onError,
}: {
  onCreated: () => Promise<void>
  onError: (msg: string) => void
}) {
  const { t } = useTranslation()
  const [slug, setSlug] = useState('')
  const [title, setTitle] = useState('')
  const [statement, setStatement] = useState('')
  const [difficulty, setDifficulty] = useState<ProblemDifficulty>('easy')
  const [tags, setTags] = useState('')
  const [templateRaw, setTemplateRaw] = useState(DEFAULT_TEMPLATE)
  const [specRaw, setSpecRaw] = useState(DEFAULT_JUDGE_SPEC)
  const [published, setPublished] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      let template: Record<string, unknown>
      let spec: Record<string, unknown>
      try {
        template = JSON.parse(templateRaw)
      } catch {
        throw new Error(t('admin.problems.invalidTemplateJson'))
      }
      try {
        spec = JSON.parse(specRaw)
      } catch {
        throw new Error(t('admin.problems.invalidSpecJson'))
      }
      await createProblem({
        slug,
        title,
        statement_md: statement,
        difficulty,
        tags: tags.split(',').map((s) => s.trim()).filter(Boolean),
        starter_template_json: template,
        judge_spec: spec,
        published,
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
      <Field label={t('admin.problems.fieldSlug')} hint="e.g. iris-knn">
        <input
          required
          pattern="^[a-z0-9-]+$"
          className="input"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
        />
      </Field>
      <Field label={t('admin.problems.fieldTitle')}>
        <input required className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <Field label={t('admin.problems.fieldDifficulty')}>
        <select className="input" value={difficulty} onChange={(e) => setDifficulty(e.target.value as ProblemDifficulty)}>
          <option value="easy">easy</option>
          <option value="medium">medium</option>
          <option value="hard">hard</option>
        </select>
      </Field>
      <Field label={t('admin.problems.fieldTags')} hint={t('admin.problems.fieldTagsHint')}>
        <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} />
      </Field>
      <Field label={t('admin.problems.fieldStatement')} className="md:col-span-2">
        <textarea rows={4} className="input font-mono text-xs" value={statement} onChange={(e) => setStatement(e.target.value)} />
      </Field>
      <Field label={t('admin.problems.fieldTemplate')} className="md:col-span-2">
        <textarea rows={10} className="input font-mono text-xs" value={templateRaw} onChange={(e) => setTemplateRaw(e.target.value)} />
      </Field>
      <Field label={t('admin.problems.fieldSpec')} className="md:col-span-2">
        <textarea rows={10} className="input font-mono text-xs" value={specRaw} onChange={(e) => setSpecRaw(e.target.value)} />
      </Field>
      <label className="flex items-center gap-2 text-sm md:col-span-2">
        <input type="checkbox" checked={published} onChange={(e) => setPublished(e.target.checked)} />
        {t('admin.problems.fieldPublishImmediately')}
      </label>
      <div className="md:col-span-2">
        <button type="submit" disabled={submitting} className="btn-primary">
          {submitting ? t('admin.problems.creating') : t('admin.problems.create')}
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
