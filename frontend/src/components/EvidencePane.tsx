'use client'

import { useState } from 'react'
import { BookOpen, FileText, Image, Table, Calculator, ExternalLink, Zap, Search, Eye, Brain } from 'lucide-react'
import { Evidence } from '@/types'

interface EvidencePaneProps {
  evidence: Evidence[]
}

// ── Evidence Image with error fallback ───────────────────────────────────────
function EvidenceImage({ src }: { src: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return (
      <div className="px-3 py-2 text-xs font-medium text-slate-500 bg-slate-50 border-t border-slate-200">
        Figure preview unavailable
      </div>
    )
  }
  return (
    <img
      src={src}
      alt="Evidence figure"
      className="w-full h-auto object-cover hover:scale-105 transition-transform duration-300"
      onError={() => setFailed(true)}
    />
  )
}

// ── v2.0: Retrieval Source Badge ──────────────────────────────────────────────
function RetrievalBadge({ source }: { source?: string | null }) {
  if (!source) return null

  const configs: Record<string, { label: string; className: string; Icon: React.ElementType }> = {
    bm25:       { label: 'Keyword',   className: 'bg-orange-50 text-orange-700 border-orange-200',  Icon: Search },
    semantic:   { label: 'Semantic',  className: 'bg-blue-50 text-blue-700 border-blue-200',        Icon: Zap },
    visual:     { label: 'Visual',    className: 'bg-purple-50 text-purple-700 border-purple-200',  Icon: Eye },
    multimodal: { label: 'Multimodal',className: 'bg-emerald-50 text-emerald-700 border-emerald-200', Icon: Brain },
    hybrid:     { label: 'Hybrid',    className: 'bg-sky-50 text-sky-700 border-sky-200',           Icon: Zap },
  }

  const cfg = configs[source] ?? { label: source, className: 'bg-slate-50 text-slate-600 border-slate-200', Icon: Search }
  const { label, className, Icon } = cfg

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${className}`}>
      <Icon className="w-2.5 h-2.5" />
      {label}
    </span>
  )
}

// ── v2.0: Per-Stage Score Bar ─────────────────────────────────────────────────
function ScoreBreakdown({ bm25, faiss, clip }: { bm25?: number | null; faiss?: number | null; clip?: number | null }) {
  const hasBreakdown = bm25 != null || faiss != null || clip != null
  if (!hasBreakdown) return null

  const bars = [
    { label: 'BM25',   value: bm25  ?? 0, color: 'bg-orange-400' },
    { label: 'FAISS',  value: faiss ?? 0, color: 'bg-blue-400'   },
    { label: 'CLIP',   value: clip  ?? 0, color: 'bg-purple-400' },
  ].filter(b => b.value > 0)

  if (bars.length === 0) return null

  return (
    <div className="mt-2 space-y-1">
      {bars.map(bar => (
        <div key={bar.label} className="flex items-center gap-1.5">
          <span className="text-[9px] font-bold text-slate-400 w-8">{bar.label}</span>
          <div className="flex-1 h-1 bg-slate-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${bar.color}`}
              style={{ width: `${Math.min(bar.value * 100, 100)}%` }}
            />
          </div>
          <span className="text-[9px] text-slate-400 w-6 text-right">
            {Math.round(bar.value * 100)}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Main EvidencePane ─────────────────────────────────────────────────────────
export default function EvidencePane({ evidence }: EvidencePaneProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  const getScoreWidthClass = (score: number) => {
    if (score >= 0.95) return 'w-full'
    if (score >= 0.9)  return 'w-11/12'
    if (score >= 0.8)  return 'w-10/12'
    if (score >= 0.7)  return 'w-8/12'
    if (score >= 0.6)  return 'w-7/12'
    if (score >= 0.5)  return 'w-6/12'
    if (score >= 0.4)  return 'w-5/12'
    if (score >= 0.3)  return 'w-4/12'
    if (score >= 0.2)  return 'w-3/12'
    if (score >= 0.1)  return 'w-2/12'
    return 'w-1/12'
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'figure':   return <Image className="w-5 h-5" />
      case 'table':    return <Table className="w-5 h-5" />
      case 'equation': return <Calculator className="w-5 h-5" />
      default:         return <FileText className="w-5 h-5" />
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'figure':
        return { bg: 'bg-blue-50 border-blue-200',     icon: 'text-blue-600',   badge: 'bg-blue-100 text-blue-700'   }
      case 'table':
        return { bg: 'bg-green-50 border-green-200',   icon: 'text-green-600',  badge: 'bg-green-100 text-green-700' }
      case 'equation':
        return { bg: 'bg-purple-50 border-purple-200', icon: 'text-purple-600', badge: 'bg-purple-100 text-purple-700' }
      default:
        return { bg: 'bg-slate-50 border-slate-200',   icon: 'text-slate-600',  badge: 'bg-slate-100 text-slate-700' }
    }
  }

  return (
    <div className="card-base h-[420px] xl:h-full flex flex-col shadow-medium overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-transparent sticky top-0">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-100 to-blue-100 rounded-lg flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-indigo-600" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-slate-900">Evidence Sources</h3>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <p className="text-xs text-slate-600 font-medium">
                {evidence.length} source{evidence.length !== 1 ? 's' : ''}
              </p>
              <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs font-semibold border border-blue-200">
                💬 Click message badges
              </span>
              {/* v2.0: Show which retrieval pipelines are active */}
              {evidence.some(ev => ev.retrieval_source) && (
                <span className="px-2 py-0.5 bg-sky-50 text-sky-600 rounded text-xs font-semibold border border-sky-200">
                  ⚡ Hybrid RAG
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Evidence Cards */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
        {evidence.map((ev, index) => {
          const colors    = getTypeColor(ev.chunk_type)
          const isExpanded = expandedIndex === index

          return (
            <div
              key={index}
              className={`border-2 rounded-lg p-4 transition-all duration-200 hover:shadow-lg hover:border-primary-300 ${colors.bg} border-current cursor-pointer group`}
              onClick={() => setExpandedIndex(isExpanded ? null : index)}
            >
              {/* Card Header */}
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center space-x-2 flex-1 min-w-0">
                  <div className={`p-2 rounded-lg bg-white border-2 border-current flex-shrink-0`}>
                    <div className={colors.icon}>{getIcon(ev.chunk_type)}</div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap mb-1">
                      {/* Chunk type badge */}
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${colors.badge}`}>
                        <span className="capitalize">{ev.chunk_type}</span>
                        {ev.page_number && (
                          <span className="ml-0.5 opacity-75">p{ev.page_number}</span>
                        )}
                      </span>
                      {/* v2.0: Retrieval source badge */}
                      <RetrievalBadge source={ev.retrieval_source} />
                      {/* v2.0: Layout label badge */}
                      {ev.layout_label && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                          🏷 {ev.layout_label}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Relevance score */}
                <div className="text-right flex-shrink-0 ml-2">
                  <div className="flex items-center space-x-1 mb-1">
                    <div className="w-14 h-2 bg-slate-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full bg-gradient-to-r from-primary-500 to-primary-400 rounded-full ${getScoreWidthClass(ev.relevance_score)}`}
                      />
                    </div>
                  </div>
                  <span className="text-xs font-bold text-slate-600">
                    {Math.round(ev.relevance_score * 100)}%
                  </span>
                </div>
              </div>

              {/* Section title */}
              {ev.section_title && (
                <p className="text-xs font-bold text-slate-700 mb-2 pb-2 border-b border-current/20">
                  📍 {ev.section_title}
                </p>
              )}

              {/* Figure image */}
              {ev.image_url && (
                <div className="mb-3 rounded-lg overflow-hidden border-2 border-current/30 bg-white">
                  <EvidenceImage src={ev.image_url} />
                </div>
              )}

              {/* Text snippet */}
              <p className={`text-sm text-slate-700 bg-white/50 p-3 rounded-lg border border-current/20 ${isExpanded ? '' : 'line-clamp-3'} transition-all`}>
                &ldquo;{ev.snippet}&rdquo;
              </p>

              {/* v2.0: Per-stage score breakdown (shown when expanded) */}
              {isExpanded && (
                <ScoreBreakdown
                  bm25={ev.bm25_score}
                  faiss={ev.faiss_score}
                  clip={ev.clip_score}
                />
              )}

              {/* Footer */}
              <div className="mt-3 pt-3 border-t border-current/20 flex items-center justify-between">
                <span className="text-xs text-slate-500 font-medium">
                  ID: {ev.chunk_id.substring(0, 8)}...
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-400">
                    {isExpanded ? '▲ collapse' : '▼ scores'}
                  </span>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}