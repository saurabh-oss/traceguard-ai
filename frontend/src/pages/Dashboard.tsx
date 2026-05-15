import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { getFailures, getPatches, getEvals, simulateFailure, wsUrl } from '../lib/api'

const SEV_BADGE: Record<string, string> = {
  critical: 'bg-red-900 text-red-300 border border-red-700',
  high:     'bg-orange-900 text-orange-300 border border-orange-700',
  medium:   'bg-yellow-900 text-yellow-300 border border-yellow-700',
  low:      'bg-green-900 text-green-300 border border-green-700',
}
const STATUS_DOT: Record<string, string> = {
  new:           'text-gray-400',
  classified:    'text-blue-400',
  patch_pending: 'text-yellow-400',
  patched:       'text-teal-400',
  resolved:      'text-green-400',
}
const PATCH_STATUS_STYLE: Record<string, string> = {
  pending:   'text-gray-400',
  pr_opened: 'text-blue-400',
  approved:  'text-teal-400',
  rejected:  'text-red-400',
  merged:    'text-green-400',
}
const DEMOS = ['infinite_loop', 'hallucination', 'tool_misuse', 'context_overflow', 'empty_response']

export default function Dashboard() {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data: failures = [], isLoading } = useQuery({
    queryKey: ['failures'], queryFn: getFailures, refetchInterval: 4000,
  })
  const { data: patches = [] } = useQuery({
    queryKey: ['patches'], queryFn: getPatches, refetchInterval: 4000,
  })
  const { data: evals = [] } = useQuery({
    queryKey: ['evals'], queryFn: getEvals, refetchInterval: 4000,
  })

  useEffect(() => {
    const ws = new WebSocket(wsUrl)
    ws.onmessage = () => {
      qc.invalidateQueries({ queryKey: ['failures'] })
      qc.invalidateQueries({ queryKey: ['patches'] })
      qc.invalidateQueries({ queryKey: ['evals'] })
    }
    return () => ws.close()
  }, [])

  // cross-reference maps
  const patchByFailure = Object.fromEntries(
    (patches as any[]).map((p: any) => [p.failure_id, p])
  )
  const evalByFailure = Object.fromEntries(
    (evals as any[]).map((e: any) => [e.failure_id, e])
  )

  // stats
  const total    = failures.length
  const resolved = (failures as any[]).filter((f: any) => f.status === 'resolved').length
  const bySev    = ['critical', 'high', 'medium', 'low'].map(s => ({
    label: s, count: (failures as any[]).filter((f: any) => f.severity === s).length,
  }))

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-bold">Failure Dashboard</h1>
        <div className="flex gap-2 flex-wrap">
          {DEMOS.map(d => (
            <button
              key={d}
              onClick={() => simulateFailure(d).then(() => qc.invalidateQueries({ queryKey: ['failures'] }))}
              className="text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded px-3 py-1.5 transition"
            >
              + {d.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-6 gap-3 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 col-span-2">
          <p className="text-xs text-gray-500 mb-1">Total Failures</p>
          <p className="text-3xl font-bold">{total}</p>
          <p className="text-xs text-green-400 mt-1">{resolved} resolved</p>
        </div>
        {bySev.map(({ label, count }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-500 mb-1 capitalize">{label}</p>
            <p className={`text-2xl font-bold ${
              label === 'critical' ? 'text-red-400' :
              label === 'high'     ? 'text-orange-400' :
              label === 'medium'   ? 'text-yellow-400' : 'text-green-400'
            }`}>{count}</p>
          </div>
        ))}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 mb-1">Patches</p>
          <p className="text-2xl font-bold text-teal-400">{patches.length}</p>
        </div>
      </div>

      {/* Failure list */}
      {isLoading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <div className="space-y-3">
          {failures.length === 0 && (
            <div className="text-center py-20 text-gray-600">
              <div className="text-5xl mb-4">🔍</div>
              <p>No failures yet. Click a button above to simulate one.</p>
            </div>
          )}
          {(failures as any[]).map((f: any) => {
            const patch = patchByFailure[f.id]
            const ev    = evalByFailure[f.id]
            const open  = expanded === f.id
            return (
              <div
                key={f.id}
                className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden hover:border-gray-700 transition"
              >
                {/* Card header — click to expand */}
                <div
                  className="p-5 cursor-pointer"
                  onClick={() => setExpanded(open ? null : f.id)}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEV_BADGE[f.severity] || 'bg-gray-800 text-gray-400'}`}>
                          {f.severity?.toUpperCase()}
                        </span>
                        <span className="text-xs text-gray-500 font-mono">{f.failure_type || 'classifying…'}</span>
                        <span className={`text-xs font-medium ${STATUS_DOT[f.status] || 'text-gray-400'}`}>
                          ● {f.status}
                        </span>
                        {patch && (
                          <span className={`text-xs ${PATCH_STATUS_STYLE[patch.status] || 'text-gray-400'}`}>
                            · patch {patch.status}
                          </span>
                        )}
                        {ev?.shadow_score_after != null && (
                          <span className="text-xs text-purple-400">
                            · shadow {ev.shadow_score_before?.toFixed(2)} → {ev.shadow_score_after?.toFixed(2)}
                          </span>
                        )}
                      </div>
                      <p className="font-semibold truncate">{f.title || 'Processing…'}</p>
                      <p className="text-sm text-gray-400 mt-0.5">{f.description || 'Classifier running…'}</p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-xs text-gray-600">{new Date(f.created_at).toLocaleTimeString()}</span>
                      <span className="text-gray-600">{open ? '▲' : '▼'}</span>
                    </div>
                  </div>
                </div>

                {/* Expanded detail */}
                {open && (
                  <div className="border-t border-gray-800 px-5 pb-5 pt-4 space-y-4">
                    {/* Root cause */}
                    {f.root_cause_summary && (
                      <div>
                        <p className="text-xs text-gray-500 font-mono mb-1">ROOT CAUSE</p>
                        <p className="text-sm text-gray-300">{f.root_cause_summary}</p>
                      </div>
                    )}

                    {/* Trace evidence */}
                    {f.trace_evidence?.length > 0 && (
                      <div>
                        <p className="text-xs text-gray-500 font-mono mb-1">TRACE EVIDENCE</p>
                        <ul className="space-y-1">
                          {f.trace_evidence.map((e: string, i: number) => (
                            <li key={i} className="text-xs bg-gray-950 rounded px-3 py-2 text-yellow-200 font-mono">
                              {e}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Linked patch */}
                    {patch && (
                      <div>
                        <p className="text-xs text-gray-500 font-mono mb-1">AUTO-PATCH</p>
                        <div className="bg-gray-950 rounded p-3 space-y-1">
                          <div className="flex items-center gap-3">
                            <span className={`text-xs font-medium ${PATCH_STATUS_STYLE[patch.status]}`}>● {patch.status}</span>
                            <span className="text-xs text-gray-500 font-mono">{patch.patch_type}</span>
                            <span className="text-xs text-gray-600 font-mono">{patch.file_path}</span>
                          </div>
                          {patch.explanation && (
                            <p className="text-xs text-gray-400">{patch.explanation}</p>
                          )}
                          {patch.pr_url && (
                            <a href={patch.pr_url} target="_blank" rel="noopener noreferrer"
                               className="text-xs text-teal-400 hover:text-teal-300">
                              → View PR {patch.pr_number ? `#${patch.pr_number}` : '(sandbox)'}
                            </a>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Linked eval */}
                    {ev && (
                      <div>
                        <p className="text-xs text-gray-500 font-mono mb-1">EVAL CASE</p>
                        <div className="bg-gray-950 rounded p-3 space-y-1">
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-teal-300 font-mono">{ev.evaluator_name}</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                              ev.auto_promoted === 'yes' ? 'bg-green-900 text-green-300' :
                              ev.auto_promoted === 'no'  ? 'bg-red-900 text-red-300' :
                              'bg-gray-800 text-gray-400'
                            }`}>
                              {ev.auto_promoted === 'yes' ? '🚀 auto-promoted' :
                               ev.auto_promoted === 'no'  ? '⏸ manual review' : '⏳ pending'}
                            </span>
                            {ev.shadow_score_before != null && (
                              <span className="text-xs text-gray-400">
                                shadow: {ev.shadow_score_before.toFixed(2)} → <span className="text-green-400">{ev.shadow_score_after?.toFixed(2)}</span>
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Run ID */}
                    <p className="text-xs text-gray-700 font-mono">run_id: {f.run_id}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
