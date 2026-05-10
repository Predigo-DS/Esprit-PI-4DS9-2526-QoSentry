'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, LogOut, Cpu, AlertTriangle, TrendingUp, Radio,
  Shield, MessageSquare, Zap, Brain, ArrowRight, Network,
  Clock, X, ChevronRight, WifiOff, RefreshCw,
} from 'lucide-react'
import { isAuthenticated, getUsername, getRole } from '@/lib/auth'
import { useAuth } from '@/hooks/useAuth'
import {
  getTelemetryStatus, runMockOptimization, getServicesHealth,
  OptimizationResponse, ServicesHealth,
} from '@/lib/api'

// ─── Alert history ────────────────────────────────────────────────────────────

interface AlertEntry {
  ts: number
  riskLevel: string
  anomalyWindows: number
  slaAlerts: number
  summary: string
}

const HISTORY_KEY = 'qosentry_alert_history'

function todayKey() {
  return new Date().toISOString().slice(0, 10)
}

function loadHistory(): AlertEntry[] {
  try {
    const raw = localStorage.getItem(`${HISTORY_KEY}_${todayKey()}`)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveHistory(entries: AlertEntry[]) {
  try {
    localStorage.setItem(`${HISTORY_KEY}_${todayKey()}`, JSON.stringify(entries))
  } catch { /* ignore */ }
}

function pushAlert(entry: AlertEntry, prev: AlertEntry[]): AlertEntry[] {
  const updated = [entry, ...prev].slice(0, 100)
  saveHistory(updated)
  return updated
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function riskColor(level: string) {
  if (level === 'critical') return 'text-red-400'
  if (level === 'high')     return 'text-orange-400'
  if (level === 'medium')   return 'text-amber-400'
  return 'text-emerald-400'
}

function riskBg(level: string) {
  if (level === 'critical') return 'bg-red-400/10 border-red-400/30'
  if (level === 'high')     return 'bg-orange-400/10 border-orange-400/30'
  if (level === 'medium')   return 'bg-amber-400/10 border-amber-400/30'
  return 'bg-emerald-400/10 border-emerald-400/30'
}

function fmtTime(ts: number) {
  return new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const router = useRouter()
  const { logout } = useAuth()
  const [username, setUsername]   = useState<string | null>(null)
  const [role, setRole]           = useState<string | null>(null)
  const [mounted, setMounted]     = useState(false)

  // live state
  const [isLive, setIsLive]           = useState(false)
  const [bufferSize, setBufferSize]   = useState(0)
  const [activeAlerts, setActiveAlerts] = useState(0)
  const [riskLevel, setRiskLevel]     = useState('low')
  const [slaStatus, setSlaStatus]     = useState<string | null>(null)
  const [lastOptRun, setLastOptRun]   = useState<number | null>(null)
  const [optRunning, setOptRunning]   = useState(false)
  const [health, setHealth]           = useState<ServicesHealth | null>(null)
  const healthTimer                   = useRef<ReturnType<typeof setInterval> | null>(null)

  // alert history panel
  const [historyOpen, setHistoryOpen] = useState(false)
  const [history, setHistory]         = useState<AlertEntry[]>([])

  const telemetryTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const optTimer       = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Auth gate ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return }
    setUsername(getUsername())
    setRole(getRole())
    setHistory(loadHistory())
    setMounted(true)
  }, [router])

  // ── Poll services health every 15 s ──────────────────────────────────────
  const fetchHealth = useCallback(async () => {
    try {
      const h = await getServicesHealth()
      setHealth(h)
    } catch {
      setHealth({ anomaly_detection: 'offline', sla_forecasting: 'offline', agent: 'offline', rag: 'offline' })
    }
  }, [])

  // ── Poll telemetry status every 5 s ───────────────────────────────────────
  const fetchTelemetry = useCallback(async () => {
    try {
      const s = await getTelemetryStatus()
      setIsLive(s.live_mode)
      setBufferSize(s.buffer_size)
    } catch {
      setIsLive(false)
    }
  }, [])

  // ── Poll optimizer every 30 s ─────────────────────────────────────────────
  const fetchOptimization = useCallback(async () => {
    setOptRunning(true)
    try {
      const res: OptimizationResponse = await runMockOptimization()

      // Ignore simulated data — only trust results from a live Mininet feed
      if (res.mock_mode) {
        setLastOptRun(Date.now())
        return
      }

      const anomalyRes  = res.anomaly_response  as Record<string, unknown>
      const slaRes      = res.sla_response      as Record<string, unknown>
      const decision    = res.optimization_decision

      const anomalyWindows = Number(anomalyRes?.anomaly_windows ?? 0)
      const slaAlerts      = Number(slaRes?.alert_count          ?? 0)
      const risk           = (decision?.risk_level ?? 'low') as string
      const summary        = (decision?.decision_summary ?? '') as string

      // Only count active alerts when agent determines risk is elevated
      const isElevated = risk === 'medium' || risk === 'high' || risk === 'critical'
      const total      = isElevated ? anomalyWindows + slaAlerts : 0

      setActiveAlerts(total)
      setRiskLevel(risk)
      setSlaStatus(isElevated && slaAlerts > 0 ? 'At Risk' : 'Nominal')
      setLastOptRun(Date.now())

      // Only push to history when risk is elevated (skip monitor-only / low-risk runs)
      if (isElevated && total > 0) {
        const entry: AlertEntry = {
          ts: Date.now(),
          riskLevel: risk,
          anomalyWindows,
          slaAlerts,
          summary,
        }
        setHistory(prev => pushAlert(entry, prev))
      }
    } catch {
      // optimizer unavailable — keep previous values
    } finally {
      setOptRunning(false)
    }
  }, [])

  useEffect(() => {
    if (!mounted) return
    fetchHealth()
    fetchTelemetry()
    fetchOptimization()
    healthTimer.current    = setInterval(fetchHealth,       15_000)
    telemetryTimer.current = setInterval(fetchTelemetry,    5_000)
    optTimer.current       = setInterval(fetchOptimization, 30_000)
    return () => {
      if (healthTimer.current)    clearInterval(healthTimer.current)
      if (telemetryTimer.current) clearInterval(telemetryTimer.current)
      if (optTimer.current)       clearInterval(optTimer.current)
    }
  }, [mounted, fetchHealth, fetchTelemetry, fetchOptimization])

  // ── Loading ────────────────────────────────────────────────────────────────
  if (!mounted) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      </div>
    )
  }

  const onlineCount = health
    ? Object.values(health).filter(v => v === 'online').length
    : null
  const aiModelsValue = health === null ? '—'
    : onlineCount === 4 ? 'All Online'
    : onlineCount === 0 ? 'Offline'
    : `${onlineCount} / 4 Online`
  const aiModelsColor = health === null ? 'text-muted'
    : onlineCount === 4 ? 'text-accent'
    : onlineCount === 0 ? 'text-danger'
    : 'text-amber-400'

  const pipeline = [
    { icon: Network,    label: 'Mininet / Ryu',      desc: 'SDN telemetry via Redis pub/sub',           color: 'text-muted',     dot: isLive ? 'bg-secondary' : 'bg-muted/40' },
    { icon: Brain,      label: 'Anomaly Detection',  desc: 'BiLSTM · TCN · Transformer autoencoders',   color: 'text-red-400',   dot: 'bg-red-400'   },
    { icon: TrendingUp, label: 'SLA Forecasting',    desc: 'TCN + BiLSTM ensemble · QoE class scoring', color: 'text-secondary', dot: 'bg-secondary' },
    { icon: Zap,        label: 'Optimization Agent', desc: 'LangGraph orchestration · tool execution',  color: 'text-primary',   dot: 'bg-primary'   },
  ]

  return (
    <div className="min-h-screen bg-background">

      {/* ── Top bar ── */}
      <header className="border-b border-border bg-surface/40 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-gradient">QoSentry</span>
          </div>
          <div className="flex items-center gap-2">
            {role === 'ADMIN' && (
              <button
                onClick={() => router.push('/admin')}
                className="flex items-center gap-2 text-sm text-secondary hover:text-secondary/80 transition-colors px-3 py-2 rounded-lg hover:bg-surface border border-secondary/30"
              >
                <Shield className="w-4 h-4" />
                Admin
              </button>
            )}
            <button
              onClick={logout}
              className="flex items-center gap-2 text-sm text-muted hover:text-text-main transition-colors px-3 py-2 rounded-lg hover:bg-surface"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-10">

        {/* ── Welcome ── */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <h1 className="text-3xl font-bold text-text-main">
            Welcome back, <span className="text-gradient">{username ?? 'User'}</span>
          </h1>
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            {role && (
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-primary/10 border border-primary/30 text-primary">
                {role}
              </span>
            )}
            {isLive ? (
              <span className="flex items-center gap-1.5 text-xs text-secondary">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-secondary" />
                </span>
                Mininet feed active · {bufferSize} rows
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-muted">
                <WifiOff className="w-3 h-3" />
                Mininet not connected
              </span>
            )}
            {lastOptRun && (
              <span className="flex items-center gap-1 text-xs text-muted">
                <RefreshCw className={`w-3 h-3 ${optRunning ? 'animate-spin text-primary' : ''}`} />
                Last scan {fmtTime(lastOptRun)}
              </span>
            )}
          </div>
        </motion.div>

        {/* ── Status strip ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        >
          {/* AI Models */}
          <div className="glass rounded-2xl p-5 border border-border">
            <div className={`inline-flex p-2 rounded-xl ${aiModelsColor === 'text-accent' ? 'bg-accent/10' : aiModelsColor === 'text-danger' ? 'bg-danger/10' : 'bg-amber-400/10'} mb-3`}>
              <Cpu className={`w-4 h-4 ${aiModelsColor}`} />
            </div>
            <p className="text-muted text-xs font-medium mb-0.5">AI Models</p>
            <p className={`text-base font-bold ${aiModelsColor}`}>{aiModelsValue}</p>
            {health && onlineCount !== null && onlineCount < 4 && (
              <p className="text-[10px] text-muted mt-1">
                {Object.entries(health).filter(([,v]) => v === 'offline').map(([k]) => k.replace('_', ' ')).join(', ')} offline
              </p>
            )}
          </div>

          {/* Active Alerts — clickable */}
          <button
            onClick={() => setHistoryOpen(true)}
            className="glass rounded-2xl p-5 border border-border hover:border-danger/40 transition-colors text-left group"
          >
            <div className="inline-flex p-2 rounded-xl bg-danger/10 mb-3">
              <AlertTriangle className="w-4 h-4 text-danger" />
            </div>
            <p className="text-muted text-xs font-medium mb-0.5 flex items-center gap-1">
              Active Alerts
              <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
            </p>
            <p className={`text-base font-bold ${activeAlerts > 0 ? 'text-danger' : 'text-emerald-400'}`}>
              {activeAlerts}
            </p>
            {history.length > 0 && (
              <p className="text-[10px] text-muted mt-1">{history.length} alerts today</p>
            )}
          </button>

          {/* SLA Status */}
          <div className="glass rounded-2xl p-5 border border-border">
            <div className={`inline-flex p-2 rounded-xl ${slaStatus === null ? 'bg-muted/10' : 'bg-primary/10'} mb-3`}>
              <TrendingUp className={`w-4 h-4 ${slaStatus === null ? 'text-muted' : 'text-primary'}`} />
            </div>
            <p className="text-muted text-xs font-medium mb-0.5">SLA Status</p>
            <p className={`text-base font-bold ${slaStatus === null ? 'text-muted' : slaStatus === 'Nominal' ? 'text-primary' : 'text-amber-400'}`}>
              {slaStatus ?? '—'}
            </p>
            {slaStatus === null && (
              <p className="text-[10px] text-muted mt-1">awaiting optimizer</p>
            )}
          </div>

          {/* Mininet Feed */}
          <div className="glass rounded-2xl p-5 border border-border">
            <div className={`inline-flex p-2 rounded-xl ${isLive ? 'bg-secondary/10' : 'bg-muted/10'} mb-3`}>
              <Radio className={`w-4 h-4 ${isLive ? 'text-secondary' : 'text-muted'}`} />
            </div>
            <p className="text-muted text-xs font-medium mb-0.5">Mininet Feed</p>
            {isLive ? (
              <p className="text-base font-bold text-secondary flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-60" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-secondary" />
                </span>
                Live
              </p>
            ) : (
              <p className="text-base font-bold text-muted flex items-center gap-1.5">
                <WifiOff className="w-3.5 h-3.5" />
                Not Active
              </p>
            )}
          </div>
        </motion.div>

        {/* ── Risk badge ── */}
        <AnimatePresence>
          {activeAlerts > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className={`glass rounded-2xl border p-4 flex items-center gap-3 ${riskBg(riskLevel)}`}
            >
              <AlertTriangle className={`w-4 h-4 shrink-0 ${riskColor(riskLevel)}`} />
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-semibold capitalize ${riskColor(riskLevel)}`}>
                  {riskLevel} risk detected — {activeAlerts} active alert{activeAlerts !== 1 ? 's' : ''}
                </p>
                {history[0]?.summary && (
                  <p className="text-xs text-muted truncate mt-0.5">{history[0].summary}</p>
                )}
              </div>
              <button
                onClick={() => setHistoryOpen(true)}
                className={`text-xs font-semibold shrink-0 ${riskColor(riskLevel)} hover:underline`}
              >
                View history
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Main actions ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
          className="grid grid-cols-1 md:grid-cols-2 gap-6"
        >
          {/* Optimization Agent */}
          <div className="glass rounded-2xl border border-primary/30 hover:border-primary/60 transition-colors p-8 flex flex-col bg-gradient-to-br from-primary/5 to-transparent">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-xl bg-primary/10">
                <Zap className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-primary font-bold">AI Agent</p>
                <h3 className="text-xl font-bold text-text-main">Network Optimization</h3>
              </div>
              {optRunning && <RefreshCw className="w-3.5 h-3.5 text-primary animate-spin ml-auto" />}
            </div>
            <p className="text-sm text-muted leading-relaxed mb-5 flex-1">
              Real-time pipeline powered by live Mininet telemetry. Anomaly detection and SLA forecasting
              feed the LangGraph orchestration agent, producing topology-aware remediation recommendations
              with full tool execution tracing.
            </p>
            <div className="flex items-center gap-2 mb-6 flex-wrap">
              {['Anomaly Detection', 'SLA Forecasting', 'LangGraph Agent'].map(tag => (
                <span key={tag} className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary font-medium">
                  {tag}
                </span>
              ))}
            </div>
            <Link
              href="/inference/optimization"
              className="inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold bg-primary text-white hover:bg-primary/90 transition-colors self-start"
            >
              Open Optimization Agent
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Chat Workspace */}
          <div className="glass rounded-2xl border border-secondary/30 hover:border-secondary/60 transition-colors p-8 flex flex-col bg-gradient-to-br from-secondary/5 to-transparent">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-xl bg-secondary/10">
                <MessageSquare className="w-6 h-6 text-secondary" />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-secondary font-bold">RAG · LLM</p>
                <h3 className="text-xl font-bold text-text-main">QoS Chat Workspace</h3>
              </div>
            </div>
            <p className="text-sm text-muted leading-relaxed mb-5 flex-1">
              Source-grounded Q&amp;A backed by Qdrant hybrid search over your network documentation.
              Multi-turn conversations with citations, document ingestion, and persistent thread history.
            </p>
            <div className="flex items-center gap-2 mb-6 flex-wrap">
              {['RAG Retrieval', 'Qdrant Search', 'Thread History'].map(tag => (
                <span key={tag} className="text-[10px] px-2 py-0.5 rounded-full bg-secondary/10 border border-secondary/20 text-secondary font-medium">
                  {tag}
                </span>
              ))}
            </div>
            <Link
              href="/chat"
              className="inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold bg-secondary text-white hover:bg-secondary/90 transition-colors self-start"
            >
              Open Chat Workspace
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </motion.div>

        {/* ── Pipeline flow ── */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
          <p className="text-xs uppercase tracking-widest text-muted font-semibold mb-4">Optimization Pipeline</p>
          <div className="glass rounded-2xl border border-border p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 sm:gap-0">
              {pipeline.map((step, i) => {
                const Icon = step.icon
                return (
                  <div key={step.label} className="flex sm:flex-1 items-center gap-3 sm:gap-0">
                    <div className="flex sm:flex-col items-center sm:items-start gap-3 sm:gap-2 flex-1 sm:px-4">
                      <div className={`w-2 h-2 rounded-full ${step.dot} shrink-0`} />
                      <div>
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <Icon className={`w-3.5 h-3.5 ${step.color}`} />
                          <span className={`text-xs font-bold ${step.color}`}>{step.label}</span>
                        </div>
                        <p className="text-[10px] text-muted leading-relaxed">{step.desc}</p>
                      </div>
                    </div>
                    {i < pipeline.length - 1 && (
                      <ArrowRight className="w-3.5 h-3.5 text-border shrink-0 hidden sm:block" />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </motion.div>

      </main>

      {/* ── Alert History Panel ── */}
      <AnimatePresence>
        {historyOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 z-40"
              onClick={() => setHistoryOpen(false)}
            />
            <motion.aside
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              className="fixed right-0 top-0 h-full w-full max-w-sm bg-surface border-l border-border z-50 flex flex-col"
            >
              <div className="flex items-center justify-between p-5 border-b border-border">
                <div>
                  <h2 className="font-bold text-text-main">Alert History</h2>
                  <p className="text-xs text-muted mt-0.5">Today · {new Date().toLocaleDateString()}</p>
                </div>
                <button
                  onClick={() => setHistoryOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-border/30 text-muted hover:text-text-main transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-5 space-y-3">
                {history.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-40 text-center">
                    <Activity className="w-8 h-8 text-muted mb-3" />
                    <p className="text-sm font-medium text-text-main">No alerts today</p>
                    <p className="text-xs text-muted mt-1">Alerts from the optimizer will appear here</p>
                  </div>
                ) : (
                  history.map((entry, i) => (
                    <div
                      key={i}
                      className={`glass rounded-xl border p-4 ${riskBg(entry.riskLevel)}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className={`text-xs font-bold uppercase ${riskColor(entry.riskLevel)}`}>
                          {entry.riskLevel} risk
                        </span>
                        <span className="flex items-center gap-1 text-[10px] text-muted">
                          <Clock className="w-3 h-3" />
                          {fmtTime(entry.ts)}
                        </span>
                      </div>
                      <div className="flex gap-4 mb-2">
                        {entry.anomalyWindows > 0 && (
                          <span className="text-[10px] text-red-400">
                            {entry.anomalyWindows} anomaly window{entry.anomalyWindows !== 1 ? 's' : ''}
                          </span>
                        )}
                        {entry.slaAlerts > 0 && (
                          <span className="text-[10px] text-amber-400">
                            {entry.slaAlerts} SLA alert{entry.slaAlerts !== 1 ? 's' : ''}
                          </span>
                        )}
                      </div>
                      {entry.summary && (
                        <p className="text-[10px] text-muted leading-relaxed line-clamp-3">{entry.summary}</p>
                      )}
                    </div>
                  ))
                )}
              </div>

              <div className="p-5 border-t border-border">
                <Link
                  href="/inference/optimization"
                  onClick={() => setHistoryOpen(false)}
                  className="flex items-center justify-center gap-2 w-full rounded-xl px-4 py-2.5 text-sm font-semibold bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20 transition-colors"
                >
                  Open Optimization Agent
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
