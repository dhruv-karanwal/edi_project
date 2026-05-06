'use client'

import { FileText, Clock, CheckCircle, AlertCircle, Loader, MoreVertical } from 'lucide-react'
import { Document } from '@/types'

interface DocumentListProps {
  documents: Document[]
  selectedDocument: Document | null
  onSelectDocument: (doc: Document) => void
}

export default function DocumentList({
  documents,
  selectedDocument,
  onSelectDocument,
}: DocumentListProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ready':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'processing':
        return <Loader className="w-4 h-4 text-yellow-500 animate-spin" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      default:
        return <Clock className="w-4 h-4 text-slate-400" />
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ready':
        return <span className="badge-success">Ready</span>
      case 'processing':
        return <span className="badge-warning">Processing</span>
      case 'failed':
        return <span className="badge-danger">Failed</span>
      default:
        return <span className="badge-base bg-slate-100 text-slate-700">Pending</span>
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="card-base flex flex-col shadow-medium overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-transparent">
        <h3 className="text-sm font-bold text-slate-900">
          Documents <span className="text-xs text-slate-500 font-medium">({documents.length})</span>
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {documents.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <FileText className="w-6 h-6 text-slate-400" />
            </div>
            <p className="text-sm font-medium">No documents yet</p>
            <p className="text-xs text-slate-400 mt-1">Upload your first document to get started</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {documents.map((doc) => (
              <button
                key={doc.id}
                onClick={() => onSelectDocument(doc)}
                className={`w-full text-left px-4 py-4 transition-all duration-200 ${
                  selectedDocument?.id === doc.id
                    ? 'bg-primary-50 border-l-4 border-primary-500 shadow-inner'
                    : 'hover:bg-slate-50 border-l-4 border-transparent'
                }`}
              >
                <div className="flex items-start space-x-3 group">
                  <FileText
                    className={`w-5 h-5 mt-1 flex-shrink-0 transition-colors ${
                      selectedDocument?.id === doc.id ? 'text-primary-600' : 'text-slate-400 group-hover:text-slate-600'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-900 truncate group-hover:text-primary-600 transition-colors">
                      {doc.filename}
                    </p>
                    <div className="flex items-center space-x-2 mt-2 flex-wrap gap-1">
                      {getStatusBadge(doc.status)}
                      <span className="text-xs text-slate-500">
                        {doc.page_count ? `${doc.page_count}p` : 'Processing'}
                      </span>
                      <span className="text-xs text-slate-400">•</span>
                      <span className="text-xs text-slate-500">
                        {formatDate(doc.created_at)}
                      </span>
                    </div>
                  </div>
                  <div className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <MoreVertical className="w-4 h-4 text-slate-400" />
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}