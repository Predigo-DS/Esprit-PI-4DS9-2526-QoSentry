'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity,
  ArrowLeft,
  Play,
  CheckCircle,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Zap,
  BarChart2,
  Shield,
  Wrench,
} from 'lucide-react'
import Link from 'next/link'
import { isAuthenticated } from '@/lib/auth'
import { runMockOptimization, OptimizationResponse, ToolTraceEntry } from '@/lib/api'

const RISK_CONFIG = {
  low:      { color: 'text-accent',   bg: 'bg-accent/10',   border: 'border-accent/30',   icon: CheckCircle  },
  medium:   { color: 'text-primary',  bg: 'bg-primary/10',  border: 'border-primary/30',  icon: AlertTriangle },
  high:     { color: 'text-orange-400', bg: 'bg-orange-400/10', border: 'border-orange-400/30', icon: AlertTriangle },
  critical: { color: 'text-danger',   bg: 'bg-danger/10',   border: 'border-danger/30',   icon: XCircle      },
}

function RiskBadge({ level }: { level: string }) {
  const cfg = RISK_CONFIG[level as keyof typeof RISK_CONFIG] ?? RISK_CONFIG.medium
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${cfg.color} ${cfg.bg} ${cfg.border}`}>
      <Icon className="w-3.5 h-3.5" />
      {level.toUpperCase()}
    </span>
  )
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'bg-accent' : pct >= 60 ? 'bg-primary' : 'bg-orange-400'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-surface rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${color}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
      <span className="text-sm font-bold text-text-main w-10 text-right">{pct}%</span>
    </div>
  )
}

function ToolTraceCard({ entry, index }: { entry: ToolTraceEntry; index: number }) {
  const [open, setOpen] = useState(false)
  const isOk = (entry.result as Record<string, unknown>)?.status === 'ok'
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className="glass rounded-xl border border-border overflow-hidden"
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${isOk ? 'bg-accent' : 'bg-danger'}`} />
          <span className="font-mono text-sm text-primary font-semibold">{entry.tool}</span>
          <span className="text-xs text-muted hidden sm:block">
            {Object.entries(entry.args).map(([k, v]) => `${k}=${v}`).join(', ')}
          </span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            className="overflow-hidden border-t border-border"
          >
            <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted font-semibold mb-2 uppercase tracking-wide">Args</p>
                <pre className="text-xs bg-surface rounded-lg p-3 text-text-main overflow-auto">
                  {JSON.stringify(entry.args, null, 2)}
                </pre>
              </div>
              <div>
                <p className="text-xs text-muted font-semibold mb-2 uppercase tracking-wide">Result</p>
                <pre className="text-xs bg-surface rounded-lg p-3 text-text-main overflow-auto">
                  {JSON.stringify(entry.result, null, 2)}
                </pre>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function MetricRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-border/40 last:border-0">
      <span className="text-xs text-muted font-mono">{label}</span>
      <span className="text-xs font-semibold text-text-main">{value.toFixed(3)}</span>
    </div>
  )
}

const KEY_METRICS = [
  'mos_voice', 'e2e_delay_ms', 'plr', 'jitter_ms',
  'streaming_mos', 'throughput_mbps', 'dataplane_latency_ms', 'ctrl_plane_rtt_ms',
]

export default function OptimizationPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<OptimizationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated()) router.replace('/login')
  }, [router])

  async function handleRun() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await runMockOptimization()

      const anomalyMock = !!(data.anomaly_response as Record<string, unknown>)?.mock
      const slaMock = !!(data.sla_response as Record<string, unknown>)?.mock

      console.group('%c[QoSentry] Optimization Pipeline Result', 'color:#7c6af7;font-weight:bold')
      console.log(
        `%cAnomaly Detection model: %c${anomalyMock ? '❌ MOCK FALLBACK (model not loaded)' : '✅ REAL MODEL used'}`,
        'color:gray', anomalyMock ? 'color:orange;font-weight:bold' : 'color:green;font-weight:bold'
      )
      console.log(
        `%cSLA Forecasting model:   %c${slaMock ? '❌ MOCK FALLBACK (model not loaded)' : '✅ REAL MODEL used'}`,
        'color:gray', slaMock ? 'color:orange;font-weight:bold' : 'color:green;font-weight:bold'
      )
      console.log('%cAnomaly response:', 'color:gray', data.anomaly_response)
      console.log('%cSLA response:', 'color:gray', data.sla_response)
      console.log('%cAgent decision:', 'color:gray', data.optimization_decision)
      console.groupEnd()

      setResult(data)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } }; message?: string })
        ?.response?.data?.message ?? (e as { message?: string })?.message ?? 'Unknown error'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const decision = result?.optimization_decision
  const recommendedActions = Array.isArray((decision as { recommended_actions?: unknown })?.recommended_actions)
    ? (decision as { recommended_actions: string[] }).recommended_actions
    : []
  const toolTrace = Array.isArray((result as { tool_trace?: unknown })?.tool_trace)
    ? (result as { tool_trace: ToolTraceEntry[] }).tool_trace
    : []
  const riskLevel = (decision?.risk_level ?? 'medium') as keyof typeof RISK_CONFIG
  const riskCfg = RISK_CONFIG[riskLevel] ?? RISK_CONFIG.medium

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-surface/40 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-gradient">QoSentry</span>
            <span className="text-muted">/</span>
            <span className="text-sm text-muted">Network Optimization</span>
          </div>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-sm text-muted hover:text-text-main transition-colors px-3 py-2 rounded-lg hover:bg-surface"
          >
            <ArrowLeft className="w-4 h-4" />
            Dashboard
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>

          {/* Title */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <div className="inline-flex p-2.5 rounded-xl bg-primary/10">
                <Zap className="w-5 h-5 text-primary" />
              </div>
              <h1 className="text-2xl font-bold text-text-main">Network Optimization Agent</h1>
            </div>
            <p className="text-sm text-muted ml-14">
              Runs the full pipeline: telemetry ingestion → anomaly detection → SLA forecasting → LangGraph agent decision.
            </p>
          </div>

          {/* Run button */}
          <div className="glass rounded-2xl border border-border p-6 mb-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-primary font-semibold mb-1">Mock Pipeline</p>
                <p className="text-sm text-muted">6 deterministic telemetry rows · anomaly + SLA fallback · LLM decision</p>
              </div>
              <button
                onClick={handleRun}
                disabled={loading}
                className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed min-w-[160px]"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                    Running…
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Run Optimization
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
              className="glass rounded-2xl border border-danger/30 bg-danger/5 p-5 mb-8 flex items-start gap-3"
            >
              <XCircle className="w-5 h-5 text-danger flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-danger mb-1">Pipeline error</p>
                <p className="text-xs text-muted">{error}</p>
              </div>
            </motion.div>
          )}

          {/* Results */}
          {result && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }} className="space-y-6">

              {/* Decision card */}
              {decision && (
                <div className={`glass rounded-2xl border ${riskCfg.border} p-6`}>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Shield className="w-5 h-5 text-primary" />
                      <h2 className="text-lg font-bold text-text-main">Agent Decision</h2>
                    </div>
                    <RiskBadge level={riskLevel} />
                  </div>

                  <p className="text-sm text-text-main mb-5 leading-relaxed">{decision.decision_summary}</p>

                  <div className="mb-5">
                    <p className="text-xs text-muted font-semibold uppercase tracking-wide mb-2">Confidence</p>
                    <ConfidenceBar value={decision.confidence} />
                  </div>

                  {recommendedActions.length > 0 && (
                    <div>
                      <p className="text-xs text-muted font-semibold uppercase tracking-wide mb-2">Recommended Actions</p>
                      <ul className="space-y-2">
                        {recommendedActions.map((action, i) => (
                          <li key={i} className="flex items-center gap-2 text-sm text-text-main">
                            <CheckCircle className="w-4 h-4 text-accent flex-shrink-0" />
                            <code className="font-mono text-xs bg-surface px-2 py-1 rounded">{action}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Tool trace */}
              {toolTrace.length > 0 && (
                <div className="glass rounded-2xl border border-border p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Wrench className="w-5 h-5 text-secondary" />
                    <h2 className="text-lg font-bold text-text-main">Tool Execution Trace</h2>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-secondary/10 text-secondary border border-secondary/30">
                      {toolTrace.length} call{toolTrace.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="space-y-3">
                    {toolTrace.map((entry, i) => (
                      <ToolTraceCard key={i} entry={entry} index={i} />
                    ))}
                  </div>
                </div>
              )}

              {/* Metrics + AI results row */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                {/* Avg metrics */}
                <div className="glass rounded-2xl border border-border p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <BarChart2 className="w-4 h-4 text-primary" />
                    <h3 className="text-sm font-bold text-text-main">30s Avg Metrics</h3>
                  </div>
                  <div>
                    {KEY_METRICS.map(k => {
                      const v = result.telemetry_summary.avg_metrics[k]
                      return v !== undefined ? <MetricRow key={k} label={k} value={v} /> : null
                    })}
                  </div>
                </div>

                {/* Anomaly */}
                <div className="glass rounded-2xl border border-border p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle className="w-4 h-4 text-orange-400" />
                    <h3 className="text-sm font-bold text-text-main">Anomaly Detection</h3>
                    {!!(result.anomaly_response as Record<string, unknown>)?.mock && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-surface text-muted border border-border">mock</span>
                    )}
                  </div>
                  <div className="space-y-3">
                    {[
                      { label: 'Anomaly Detected', value: String((result.anomaly_response as Record<string, unknown>)?.anomaly_detected ?? '—') },
                      { label: 'Anomaly Score', value: String((result.anomaly_response as Record<string, unknown>)?.anomaly_score ?? '—') },
                      { label: 'Label', value: String((result.anomaly_response as Record<string, unknown>)?.label ?? '—') },
                      { label: 'Threshold', value: String((result.anomaly_response as Record<string, unknown>)?.threshold ?? '—') },
                    ].map(row => (
                      <div key={row.label} className="flex justify-between border-b border-border/40 pb-2 last:border-0">
                        <span className="text-xs text-muted">{row.label}</span>
                        <span className="text-xs font-semibold text-text-main">{row.value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* SLA */}
                <div className="glass rounded-2xl border border-border p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-4 h-4 text-secondary" />
                    <h3 className="text-sm font-bold text-text-main">SLA Forecasting</h3>
                    {!!(result.sla_response as Record<string, unknown>)?.mock && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-surface text-muted border border-border">mock</span>
                    )}
                  </div>
                  <div className="space-y-3">
                    {[
                      { label: 'SLA Alert', value: String((result.sla_response as Record<string, unknown>)?.sla_alert ?? '—') },
                      { label: 'Violation Prob.', value: String((result.sla_response as Record<string, unknown>)?.sla_violation_probability ?? '—') },
                      { label: 'Risk Level', value: String((result.sla_response as Record<string, unknown>)?.risk_level ?? '—') },
                    ].map(row => (
                      <div key={row.label} className="flex justify-between border-b border-border/40 pb-2 last:border-0">
                        <span className="text-xs text-muted">{row.label}</span>
                        <span className="text-xs font-semibold text-text-main">{row.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Footer info */}
              <div className="flex items-center gap-2 text-xs text-muted">
                <span>{result.telemetry_summary.row_count} telemetry rows</span>
                <span>·</span>
                <span>{result.telemetry_summary.window_seconds}s window</span>
                {result.mock_mode && (
                  <>
                    <span>·</span>
                    <span className="px-1.5 py-0.5 rounded bg-surface border border-border">mock mode</span>
                  </>
                )}
              </div>

            </motion.div>
          )}

        </motion.div>
      </main>
    </div>
  )
}

// needed for the SLA icon imported in JSX
function TrendingUp({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  )
}
