import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getPatches, approvePatch, rejectPatch } from '../lib/api'
import { useState } from 'react'

const STATUS_STYLE: Record<string,string> = {
  pending:    'text-gray-400',
  pr_opened:  'text-blue-400',
  approved:   'text-teal-400',
  rejected:   'text-red-400',
  merged:     'text-green-400',
}

export default function PatchReview() {
  const qc = useQueryClient()
  const { data: patches = [] } = useQuery({
    queryKey: ['patches'], queryFn: getPatches, refetchInterval: 5000
  })
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Patch Review</h1>
      {patches.length === 0 && (
        <div className="text-center py-20 text-gray-600">
          <div className="text-5xl mb-4">🔧</div>
          <p>No patches yet. Simulate a failure on the Dashboard first.</p>
        </div>
      )}
      <div className="space-y-4">
        {patches.map((p: any) => (
          <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-5 flex items-start justify-between gap-4 cursor-pointer"
                 onClick={() => setExpanded(expanded === p.id ? null : p.id)}>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <span className={`text-xs font-medium ${STATUS_STYLE[p.status] || 'text-gray-400'}`}>● {p.status}</span>
                  <span className="text-xs text-gray-500 font-mono">{p.patch_type}</span>
                  <span className="text-xs text-gray-600 font-mono">{p.file_path}</span>
                </div>
                <p className="text-sm text-gray-300">{p.explanation || 'Generating explanation…'}</p>
                {p.pr_url && (
                  <a href={p.pr_url} target="_blank" rel="noopener noreferrer"
                     className="text-xs text-teal-400 hover:text-teal-300 mt-1 inline-block">
                    → View PR {p.pr_number ? `#${p.pr_number}` : '(sandbox)'}
                  </a>
                )}
              </div>
              <span className="text-gray-500 text-xl">{expanded === p.id ? '▲' : '▼'}</span>
            </div>
            {expanded === p.id && (
              <div className="border-t border-gray-800 p-5 space-y-4">
                {p.diff && (
                  <div>
                    <p className="text-xs text-gray-500 mb-2 font-mono">DIFF</p>
                    <pre className="text-xs bg-gray-950 rounded p-3 overflow-x-auto text-green-300 whitespace-pre-wrap">{p.diff}</pre>
                  </div>
                )}
                {p.patched_code && (
                  <div>
                    <p className="text-xs text-gray-500 mb-2 font-mono">PATCHED CODE</p>
                    <pre className="text-xs bg-gray-950 rounded p-3 overflow-x-auto text-blue-200 whitespace-pre-wrap">{p.patched_code}</pre>
                  </div>
                )}
                {['pending','pr_opened'].includes(p.status) && (
                  <div className="flex gap-3">
                    <button onClick={() => approvePatch(p.id).then(() => qc.invalidateQueries({queryKey:['patches']}))}
                      className="px-4 py-2 bg-teal-700 hover:bg-teal-600 rounded-lg text-sm font-medium transition">
                      ✅ Approve & Merge
                    </button>
                    <button onClick={() => rejectPatch(p.id, 'Rejected via UI').then(() => qc.invalidateQueries({queryKey:['patches']}))}
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