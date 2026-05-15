import { useQuery } from '@tanstack/react-query'
import { getEvals } from '../lib/api'

export default function EvalVault() {
  const { data: evals = [] } = useQuery({
    queryKey: ['evals'], queryFn: getEvals, refetchInterval: 5000
  })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Eval Vault</h1>
      {evals.length === 0 && (
        <div className="text-center py-20 text-gray-600">
          <div className="text-5xl mb-4">🧪</div>
          <p>Evaluators appear here after failures are classified.</p>
        </div>
      )}
      <div className="space-y-4">
        {evals.map((e: any) => (
          <div key={e.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <span className="font-mono text-teal-300 text-sm">{e.evaluator_name}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                e.auto_promoted === 'yes' ? 'bg-green-900 text-green-300' :
                e.auto_promoted === 'no'  ? 'bg-red-900 text-red-300' :
                'bg-gray-800 text-gray-400'
              }`}>{e.auto_promoted === 'yes' ? '🚀 Auto-promoted' :
                   e.auto_promoted === 'no'  ? '⏸ Manual review' : '⏳ Pending'}</span>
              {e.shadow_score_before != null && (
                <span className="text-xs text-gray-500">
                  Shadow: {e.shadow_score_before.toFixed(2)} → <span className="text-green-400">{e.shadow_score_after?.toFixed(2)}</span>
                </span>
              )}
            </div>
            {e.evaluator_code && (
              <pre className="text-xs bg-gray-950 rounded p-3 overflow-x-auto text-gray-300 whitespace-pre-wrap max-h-48">
                {e.evaluator_code}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}