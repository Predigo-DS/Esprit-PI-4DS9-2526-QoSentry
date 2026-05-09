'use client'

import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'
import { TrendingUp, ShieldAlert, Zap, MessageSquare } from 'lucide-react'

const features = [
  {
    icon: ShieldAlert,
    title: 'Anomaly Detection',
    description:
      'Ensemble of three autoencoder architectures — BiLSTM, TCN, and Transformer — detect anomalous network windows in real time via reconstruction error scoring against configurable thresholds.',
    tag: 'BiLSTM · TCN · Transformer',
    gradient: 'from-primary/20 to-primary/5',
    border: 'border-primary/20 hover:border-primary/60',
    tagColor: 'bg-primary/10 text-primary border-primary/30',
    iconColor: 'text-primary',
    iconBg: 'bg-primary/10',
  },
  {
    icon: TrendingUp,
    title: 'SLA Forecasting',
    description:
      'Dual ensemble of TCN and BiLSTM models predicts future QoE classes and SLA breach risk windows from raw telemetry. Outputs per-window class probabilities and alert flags before breaches occur.',
    tag: 'TCN · BiLSTM Ensemble',
    gradient: 'from-secondary/20 to-secondary/5',
    border: 'border-secondary/20 hover:border-secondary/60',
    tagColor: 'bg-secondary/10 text-secondary border-secondary/30',
    iconColor: 'text-secondary',
    iconBg: 'bg-secondary/10',
  },
  {
    icon: Zap,
    title: 'Optimization Agent',
    description:
      'LangGraph-orchestrated agent pipeline: ingests live telemetry, runs anomaly detection and SLA forecasting, then generates topology-aware remediation recommendations with full tool execution tracing.',
    tag: 'LangGraph · Multi-model',
    gradient: 'from-accent/20 to-accent/5',
    border: 'border-accent/20 hover:border-accent/60',
    tagColor: 'bg-accent/10 text-accent border-accent/30',
    iconColor: 'text-accent',
    iconBg: 'bg-accent/10',
  },
  {
    icon: MessageSquare,
    title: 'RAG Chat Workspace',
    description:
      'Qdrant-backed retrieval with hybrid dense and sparse search grounds every LLM response in your network documentation. Multi-turn chat with source citations, document ingestion, and thread persistence.',
    tag: 'RAG · Qdrant · LLM',
    gradient: 'from-danger/20 to-danger/5',
    border: 'border-danger/20 hover:border-danger/60',
    tagColor: 'bg-danger/10 text-danger border-danger/30',
    iconColor: 'text-danger',
    iconBg: 'bg-danger/10',
  },
]

const fadeInUp = {
  hidden: { y: 40, opacity: 0 },
  visible: { y: 0, opacity: 1 },
}

export default function Features() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-100px' })

  return (
    <section id="features" ref={ref} className="py-24 bg-surface/20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-block px-3 py-1 text-xs font-semibold rounded-full bg-secondary/10 border border-secondary/30 text-secondary tracking-wide uppercase mb-4">
            Core Capabilities
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            The AI stack behind{' '}
            <span className="text-gradient">QoSentry</span>
          </h2>
          <p className="text-muted max-w-2xl mx-auto">
            From raw telemetry to remediation — anomaly detection, SLA forecasting, an orchestration
            agent, and a RAG chat workspace working together in a unified platform.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((f, i) => {
            const Icon = f.icon
            return (
              <motion.div
                key={f.title}
                variants={fadeInUp}
                initial="hidden"
                animate={inView ? 'visible' : 'hidden'}
                transition={{ duration: 0.6, delay: i * 0.15 }}
                className={`group relative glass rounded-2xl p-8 border transition-all duration-300 ${f.border}`}
              >
                {/* Background gradient */}
                <div
                  className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${f.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`}
                />

                <div className="relative z-10">
                  <div className="flex items-start justify-between mb-4">
                    <div className={`p-3 rounded-xl ${f.iconBg}`}>
                      <Icon className={`w-6 h-6 ${f.iconColor}`} />
                    </div>
                    <span
                      className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${f.tagColor} font-mono`}
                    >
                      {f.tag}
                    </span>
                  </div>
                  <h3 className="text-xl font-bold text-text-main mb-3">{f.title}</h3>
                  <p className="text-muted leading-relaxed text-sm">{f.description}</p>
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
