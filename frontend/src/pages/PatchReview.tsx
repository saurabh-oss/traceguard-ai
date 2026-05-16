import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getPatches, approvePatch, rejectPatch } from '../lib/api'
import { useState } from 'react'

const STATUS_STYLE: Record<string, string> = {
  pending:   'text-gray-400',
  pr_opened: 'text-blue-400',
  approved:  'text-teal-400',
  rejected:  'text-red-400',
  merged:    'text-green-400',
}

function DiffViewer({ diff }: { diff: string }) {
  if (!diff?.trim()) return null
  return (
    <div className="rounded overflow-hidden border border-gray-800 text-xs font-mono">
      {diff.split('\n').map((line, i) => {
        let cls = 'px-3 py-[1px] text-gray-500 bg-transparent'
        if (line.startsWith('+++') || line.startsWith('---'))
          cls = 'px-3 py-[1px] text-gray-400 bg-gray-800/60'
        else if (line.startsWith('@@'))
          cls = 'px-3 py-[1px] text-blue-300 bg-blue-950/40'
        else if (line.startsWith('+'))
          cls = 'px-3 py-[1px] text-green-300 bg-green-950/50'
        else if (line.startsWith('-'))
          cls = 'px-3 py-[1px] text-red-300 bg-red-950/40'
        return <div key={i} className={cls}>{line || ' '}</div>
      })}
    </div>
  )
}

function RejectModal({ onConfirm, onCancel }: {
  onConfirm: (notes: string) => void
  onCancel: () => void
}) {
  const [notes, setNotes] = useState('')
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md space-y-4">
        <h2 className="font-semibold text-lg">Reject patch</h2>
        <p className="text-sm text-gray-400">
          Add reviewer notes so TraceGuard can generate a better fix automatically.
        </p>
        <textarea
          className="w-full bg-gray-950 border border-gray-700 rounded-lg p-3 text-sm resize-none focus:outline-none focus:border-teal-600"
          rows={4}
          placeholder="e.g. The guard should use a configurable limit, not hardcoded 10…"
          value={notes}
          onChange={e => setNotes(e.target.value)}
        />
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition">
            Cancel
          </button>
          <button onClick={() => onConfirm(notes)}
            className="px-4 py-2 bg-red-900 hover:bg-red-800 rounded-lg text-sm font-medium transition">
            Reject {notes.trim() ? '& Re-patch' : ''}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function PatchReview() {
  const qc = useQueryClient()
  const { data: patches = [] } = useQuery({
    queryKey: ['patches'], queryFn: getPatches, refetchInterval: 5000,
  })
  const [expanded, setExpanded] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState<string | null>(null)

  const handleApprove = (id: string) =>
    approvePatch(id).then(() => qc.invalidateQueries({ queryKey: ['patches'] }))

  const handleReject = (id: string, notes: string) => {
    setRejecting(null)
    rejectPatch(id, notes).then(() => qc.invalidateQueries({ queryKey: ['patches'] }))
  }

  return (
    <div>
      {rejecting && (
        <RejectModal
          onConfirm={notes => handleReject(rejecting, notes)}
          onCancel={() => setRejecting(null)}
        />
      )}

      <h1 className="text-2xl font-bold mb-6">Patch Review</h1>

      {patches.length === 0 && (
        <div className="text-center py-20 text-gray-600">
          <div className="text-5xl mb-4">🔧</div>
          <p>No patches yet. Simulate a failure on the Dashboard first.</p>
        </div>
      )}

      <div className="space-y-4">
        {(patches as any[]).map((p: any) => (
          <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            {/* Header */}
            <div className="p-5 flex items-start justify-between gap-4 cursor-pointer"
                 onClick={() => setExpanded(expanded === p.id ? null : p.id)}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-1 flex-wrap">
                  <span className={`text-xs font-medium ${STATUS_STYLE[p.status] || 'text-gray-400'}`}>
                    ● {p.status}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">{p.patch_type}</span>
                  <span className="text-xs text-gray-600 font-mono truncate max-w-[200px]">{p.file_path}</span>
                </div>
                <p className="text-sm text-gray-300">{p.explanation || 'Generating…'}</p>
                {p.pr_url && (
                  <a href={p.pr_url} target="_blank" rel="noopener noreferrer"
                     className="text-xs text-teal-400 hover:text-teal-300 mt-1 inline-block">
                    → View PR {p.pr_number ? `#${p.pr_number}` : '(sandbox)'}
                  </a>
                )}
                {p.reviewer_notes && (
                  <p className="text-xs text-yellow-600 mt-1">Note: {p.reviewer_notes}</p>
                )}
              </div>
              <span className="text-gray-500 text-xl shrink-0">{expanded === p.id ? '▲' : '▼'}</span>
            </div>

            {/* Expanded */}
            {expanded === p.id && (
              <div className="border-t border-gray-800 p-5 space-y-4">
                {p.diff && (
                  <div>
                    <p className="text-xs text-gray-500 mb-2 font-mono">DIFF</p>
                    <DiffViewer diff={p.diff} />
                  </div>
                )}

                {p.patched_code && (
                  <div>
                    <p className="text-xs text-gray-500 mb-2 font-mono">PATCHED CODE</p>
                    <pre className="text-xs bg-gray-950 border border-gray-800 rounded-lg p-4 overflow-x-auto text-blue-200 whitespace-pre leading-relaxed">
                      {p.patched_code}
                    </pre>
                  </div>
                )}

                {['pending', 'pr_opened'].includes(p.status) && (
                  <div className="flex gap-3">
                    <button onClick={() => handleApprove(p.id)}
                      className="px-4 py-2 bg-teal-700 hover:bg-teal-600 rounded-lg text-sm font-medium transition">
                      ✅ Approve & Merge
                    </button>
                    <button onClick={() => setRejecting(p.id)}
                      className="px-4 py-2 bg-red-900 hover:bg-red-800 rounded-lg text-sm font-medium transition">
                      ❌ Reject
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
