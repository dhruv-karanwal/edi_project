'use client'

import { useState } from 'react'
import { BookOpen, FileText, Image, Table, Calculator, ExternalLink } from 'lucide-react'
import { Evidence } from '@/types'

interface EvidencePaneProps {
  evidence: Evidence[]
}

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

export default function EvidencePane({ evidence }: EvidencePaneProps) {
  const getScoreWidthClass = (score: number) => {
    if (score >= 0.95) return 'w-full'
    if (score >= 0.9) return 'w-11/12'
    if (score >= 0.8) return 'w-10/12'
    if (score >= 0.7) return 'w-8/12'
    if (score >= 0.6) return 'w-7/12'
    if (score >= 0.5) return 'w-6/12'
    if (score >= 0.4) return 'w-5/12'
    if (score >= 0.3) return 'w-4/12'
    if (score >= 0.2) return 'w-3/12'
    if (score >= 0.1) return 'w-2/12'
    return 'w-1/12'
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'figure':
        return <Image className="w-5 h-5" />
      case 'table':
        return <Table className="w-5 h-5" />
      case 'equation':
        return <Calculator className="w-5 h-5" />
      default:
        return <FileText className="w-5 h-5" />
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'figure':
        return {
          bg: 'bg-blue-50 border-blue-200',
          icon: 'text-blue-600',
          badge: 'bg-blue-100 text-blue-700'
        }
      case 'table':
        return {
          bg: 'bg-green-50 border-green-200',
          icon: 'text-green-600',
          badge: 'bg-green-100 text-green-700'
        }
      case 'equation':
        return {
          bg: 'bg-purple-50 border-purple-200',
          icon: 'text-purple-600',
          badge: 'bg-purple-100 text-purple-700'
        }
      default:
        return {
          bg: 'bg-slate-50 border-slate-200',
          icon: 'text-slate-600',
          badge: 'bg-slate-100 text-slate-700'
        }
    }
  }

  return (
    <div className="card-base h-[420px] xl:h-full flex flex-col shadow-medium overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-transparent sticky top-0">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-100 to-blue-100 rounded-lg flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-indigo-600" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-slate-900">Evidence Sources</h3>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-xs text-slate-600 font-medium">{evidence.length} source{evidence.length !== 1 ? 's' : ''}</p>
              <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs font-semibold border border-blue-200">💬 Click message badges</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
        {evidence.map((ev, index) => {
          const colors = getTypeColor(ev.chunk_type)
          return (
            <div
              key={index}
              className={`border-2 rounded-lg p-4 transition-all duration-200 hover:shadow-lg hover:border-primary-300 ${colors.bg} border-current cursor-pointer group`}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-3 flex-1">
                  <div className={`p-2 rounded-lg bg-white border-2 border-current`}>
                    <div className={colors.icon}>
                      {getIcon(ev.chunk_type)}
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${colors.badge} mb-1`}>
                      <span className="capitalize">{ev.chunk_type}</span>
                      {ev.page_number && (
                        <span className="ml-1 text-xs font-normal opacity-75">
                          p{ev.page_number}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="flex items-center space-x-1 mb-1">
                    <div className="w-16 h-2 bg-slate-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full bg-gradient-to-r from-primary-500 to-primary-400 rounded-full transition-all ${getScoreWidthClass(ev.relevance_score)}`}
                      />
                    </div>
                  </div>
                  <span className="text-xs font-bold text-slate-600">
                    {Math.round(ev.relevance_score * 100)}% match
                  </span>
                </div>
              </div>

              {/* Section */}
              {ev.section_title && (
                <p className="text-xs font-bold text-slate-700 mb-3 pb-3 border-b border-current/20">
                  📍 {ev.section_title}
                </p>
              )}

              {/* Image */}
              {ev.image_url && (
                <div className="mb-3 rounded-lg overflow-hidden border-2 border-current/30 bg-white">
                  <EvidenceImage src={ev.image_url} />
                </div>
              )}

              {/* Snippet */}
              <p className="text-sm text-slate-700 line-clamp-3 bg-white/50 p-3 rounded-lg border border-current/20 group-hover:line-clamp-none transition-all">
                "{ev.snippet}"
              </p>

              {/* Footer */}
              <div className="mt-3 pt-3 border-t border-current/20 flex items-center justify-between">
                <span className="text-xs text-slate-500 font-medium">
                  ID: {ev.chunk_id.substring(0, 8)}...
                </span>
                <ExternalLink className="w-3.5 h-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}