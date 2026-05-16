import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useTranslation } from 'react-i18next'
import {
  getContest,
  getLeaderboard,
  joinContest,
  streamLeaderboard,
  type Contest,
  type Leaderboard,
} from '../api/contests'

type LeaderboardConnectionState = 'connecting' | 'live' | 'polling'

export function ContestDetail() {
  const { slug } = useParams<{ slug: string }>()
  const { t } = useTranslation()
  const [contest, setContest] = useState<Contest | null>(null)
  const [leaderboard, setLeaderboard] = useState<Leaderboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [joining, setJoining] = useState(false)
  const [liveState, setLiveState] = useState<LeaderboardConnectionState>('connecting')
  const pollHandleRef = useRef<number | null>(null)

  async function refresh() {
    if (!slug) return
    try {
      const [c, lb] = await Promise.all([getContest(slug), getLeaderboard(slug)])
      setContest(c)
      setLeaderboard(lb)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.loadFailed'))
    }
  }

  useEffect(() => {
    void refresh()
  }, [slug])

  // Live leaderboard: SSE primary, polling fallback.
  useEffect(() => {
    if (!slug) return
    let cancelled = false
    setLiveState('connecting')

    const stopPolling = () => {
      if (pollHandleRef.current !== null) {
        window.clearInterval(pollHandleRef.current)
        pollHandleRef.current = null
      }
    }
    const startPolling = () => {
      if (pollHandleRef.current !== null) return
      pollHandleRef.current = window.setInterval(() => {
        if (cancelled) return
        getLeaderboard(slug)
          .then((lb) => !cancelled && setLeaderboard(lb))
          .catch(() => {})
      }, 5000)
    }

    const source = streamLeaderboard(slug, {
      onOpen: () => {
        if (cancelled) return
        stopPolling()
        setLiveState('live')
      },
      onSnapshot: (lb) => {
        if (cancelled) return
        setLeaderboard(lb)
      },
      onError: () => {
        if (cancelled) return
        // EventSource auto-reconnects on transient errors, but flip to
        // polling so the user keeps getting updates if the server can't
        // stream at all.
        setLiveState('polling')
        startPolling()
      },
    })

    return () => {
      cancelled = true
      source.close()
      stopPolling()
    }
  }, [slug])

  async function handleJoin() {
    if (!slug) return
    setJoining(true)
    try {
      const updated = await joinContest(slug)
      setContest(updated)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('contests.detail.joinFailed'))
    } finally {
      setJoining(false)
    }
  }

  if (error) return <div className="text-rose-400">{error}</div>
  if (!contest) return <div className="text-text-muted">{t('common.loading')}</div>

  const canSubmit = contest.runtime_status === 'active' && contest.joined
  const statusLabel = t(`contests.status.${contest.runtime_status}` as const)

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
      <article>
        <div className="font-mono text-sm text-text-muted">{contest.slug}</div>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">{contest.title}</h1>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-muted">
          <span>{t('contests.detail.statusLabel', { value: statusLabel })}</span>
          <span>•</span>
          <span>
            {t('contests.detail.participants', { count: contest.participant_count })}
          </span>
          <span>•</span>
          <span>{new Date(contest.start_at).toLocaleString()}</span>
          <span>—</span>
          <span>{new Date(contest.end_at).toLocaleString()}</span>
        </div>

        {contest.description_md && (
          <div className="prose-oj mt-8">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{contest.description_md}</ReactMarkdown>
          </div>
        )}

        <section className="mt-10">
          <h2 className="text-lg font-semibold">{t('contests.detail.problems')}</h2>
          <div className="mt-3 overflow-hidden rounded-lg border border-border bg-surface">
            {contest.problems.length === 0 ? (
              <div className="p-5 text-text-muted">{t('contests.detail.noProblems')}</div>
            ) : (
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">{t('contests.detail.colNo')}</th>
                    <th className="px-4 py-3 font-medium">{t('contests.detail.colProblem')}</th>
                    <th className="px-4 py-3 font-medium">{t('contests.detail.colPoints')}</th>
                  </tr>
                </thead>
                <tbody>
                  {contest.problems.map((p, idx) => (
                    <tr
                      key={p.problem_id}
                      className="border-b border-border last:border-0 hover:bg-bg/50"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-text-muted">{idx + 1}</td>
                      <td className="px-4 py-3">
                        <Link
                          to={`/problems/${p.problem_slug}`}
                          className="text-text hover:text-accent"
                        >
                          {p.problem_title}
                        </Link>
                      </td>
                      <td className="px-4 py-3 font-mono text-text-muted">{p.points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section className="mt-10">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">{t('contests.detail.leaderboard')}</h2>
            <div className="flex items-center gap-2 text-xs">
              <span
                className={
                  liveState === 'live'
                    ? 'h-2 w-2 animate-pulse rounded-full bg-emerald-400'
                    : liveState === 'polling'
                      ? 'h-2 w-2 rounded-full bg-amber-400'
                      : 'h-2 w-2 animate-pulse rounded-full bg-text-muted'
                }
                aria-hidden
              />
              <span className="font-mono uppercase tracking-wider text-text-muted">
                {liveState === 'live'
                  ? t('contests.detail.live')
                  : liveState === 'polling'
                    ? t('contests.detail.polling')
                    : t('contests.detail.connecting')}
              </span>
              {leaderboard?.generated_at && (
                <span className="text-text-muted">
                  · {new Date(leaderboard.generated_at).toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
          <div className="mt-3 overflow-hidden rounded-lg border border-border bg-surface">
            {leaderboard && leaderboard.entries.length > 0 ? (
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">{t('contests.detail.colRank')}</th>
                    <th className="px-4 py-3 font-medium">{t('contests.detail.colParticipant')}</th>
                    <th className="px-4 py-3 font-medium">{t('contests.detail.colTotal')}</th>
                    {contest.problems.map((p) => (
                      <th
                        key={p.problem_id}
                        className="px-3 py-3 text-center font-medium"
                      >
                        {p.problem_slug}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.entries.map((e) => (
                    <tr
                      key={e.user_id}
                      className="border-b border-border last:border-0"
                    >
                      <td className="px-4 py-3 font-mono">{e.rank}</td>
                      <td className="px-4 py-3">{e.display_name}</td>
                      <td className="px-4 py-3 font-mono font-semibold">
                        {e.total_score.toFixed(2)}
                      </td>
                      {contest.problems.map((p) => (
                        <td
                          key={p.problem_id}
                          className="px-3 py-3 text-center font-mono text-text-muted"
                        >
                          {e.per_problem[p.problem_id] !== undefined
                            ? e.per_problem[p.problem_id].toFixed(1)
                            : '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-5 text-text-muted">{t('contests.detail.noEntries')}</div>
            )}
          </div>
        </section>
      </article>

      <aside className="space-y-4">
        <section className="rounded-lg border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold text-text-muted">
            {t('contests.detail.participation')}
          </h2>
          {contest.joined ? (
            <div className="mt-3 flex items-center gap-2 text-sm">
              <span className="rounded bg-accent/20 px-2 py-1 text-xs text-accent">
                {t('contests.detail.joined')}
              </span>
              {canSubmit ? (
                <span className="text-text-muted">{t('contests.detail.canSubmit')}</span>
              ) : (
                <span className="text-text-muted">
                  {contest.runtime_status === 'upcoming'
                    ? t('contests.detail.waitingToStart')
                    : contest.runtime_status === 'past'
                      ? t('contests.detail.ended')
                      : ''}
                </span>
              )}
            </div>
          ) : (
            <button
              onClick={handleJoin}
              disabled={joining || contest.runtime_status === 'past'}
              className="btn-primary mt-3 w-full"
            >
              {joining
                ? t('contests.detail.joining')
                : contest.runtime_status === 'past'
                  ? t('contests.detail.ended')
                  : t('contests.detail.join')}
            </button>
          )}
        </section>
        <section className="rounded-lg border border-border bg-surface p-5 text-xs text-text-muted">
          <h2 className="mb-2 text-sm font-semibold text-text">{t('contests.detail.schedule')}</h2>
          <div>
            {t('contests.detail.startAt', { at: new Date(contest.start_at).toLocaleString() })}
          </div>
          <div>
            {t('contests.detail.endAt', { at: new Date(contest.end_at).toLocaleString() })}
          </div>
          <div className="mt-2">
            {t('contests.detail.visibility', { value: contest.visibility })}
          </div>
        </section>
      </aside>
    </div>
  )
}
