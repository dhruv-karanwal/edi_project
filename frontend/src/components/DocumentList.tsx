'use client'

import { useState } from 'react'
import { FileText, Clock, CheckCircle, AlertCircle, Loader, Search, Eye, Layout, Trash2, RefreshCw } from 'lucide-react'
import { Document } from '@/types'
import { deleteDocument } from '@/lib/api'

interface DocumentListProps {
  documents: Document[]
  selectedDocument: Document | null
  onSelectDocument: (doc: Document) => void
  onRefresh?: () => void
}

export default function DocumentList({
  documents,
  selectedDocument,
  onSelectDocument,
  onRefresh,
}: DocumentListProps) {
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ready':
        return <CheckCircle className="w-4 h-4 text-green-500 animate-fade-in" />
      case 'processing':
        return <Loader className="w-4 h-4 text-yellow-500 animate-spin" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500 animate-pulse" />
      default:
        return <Clock className="w-4 h-4 text-slate-400" />
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ready':
        return <span className="badge-success">Ready</span>
      case 'processing':
        return <span className="badge-warning animate-pulse">Processing</span>
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

  const handleManualRefresh = async () => {
    if (isRefreshing || !onRefresh) return
    setIsRefreshing(true)
    try {
      await onRefresh()
    } finally {
      setTimeout(() => setIsRefreshing(false), 600) // Ensure visual feedback
    }
  }

  const handleConfirmDelete = async () => {
    if (!documentToDelete) return
    setIsDeleting(true)
    try {
      await deleteDocument(documentToDelete.id)
      setDocumentToDelete(null)
      if (onRefresh) {
        await onRefresh()
      }
    } catch (error) {
      console.error('Failed to delete document:', error)
      alert('Failed to delete document. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div className="card-base flex flex-col shadow-medium overflow-hidden border border-slate-200">
      {/* List Header with Refresh Button */}
      <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
          <span>Documents</span>
          <span className="text-xs text-slate-500 font-medium">({documents.length})</span>
        </h3>
        {onRefresh && (
          <button
            type="button"
            onClick={handleManualRefresh}
            disabled={isRefreshing}
            className="p-1.5 text-slate-500 hover:text-primary-600 hover:bg-slate-200/60 rounded-lg transition-all active:scale-95 disabled:opacity-50"
            title="Refresh documents"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-primary-600' : ''}`} />
          </button>
        )}
      </div>

      {/* List Scroll Area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin max-h-[360px] xl:max-h-none">
        {documents.length === 0 ? (
          <div className="p-8 text-center text-slate-500 bg-white">
            <div className="w-12 h-12 bg-slate-100 rounded-xl flex items-center justify-center mx-auto mb-3">
              <FileText className="w-6 h-6 text-slate-400" />
            </div>
            <p className="text-sm font-bold text-slate-700">No documents yet</p>
            <p className="text-xs text-slate-500 mt-1">Upload a research paper or document above to begin analysis.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-200 bg-white">
            {documents.map((doc) => {
              const isSelected = selectedDocument?.id === doc.id
              return (
                <div
                  key={doc.id}
                  onClick={() => onSelectDocument(doc)}
                  className={`w-full flex items-start justify-between px-4 py-4 transition-all duration-200 cursor-pointer group border-l-4 ${
                    isSelected
                      ? 'bg-primary-50/70 border-primary-500 shadow-inner'
                      : 'hover:bg-slate-50/50 border-transparent'
                  }`}
                >
                  <div className="flex items-start space-x-3 min-w-0 flex-1">
                    <div className="mt-0.5 flex-shrink-0">
                      {getStatusIcon(doc.status)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-slate-800 truncate group-hover:text-primary-700 transition-colors">
                        {doc.filename}
                      </p>
                      
                      <div className="flex items-center space-x-2 mt-1.5 flex-wrap gap-y-1">
                        {getStatusBadge(doc.status)}
                        <span className="text-xs font-medium text-slate-500">
                          {doc.page_count ? `${doc.page_count} page${doc.page_count !== 1 ? 's' : ''}` : 'Analysing'}
                        </span>
                        <span className="text-xs text-slate-400 font-bold">•</span>
                        <span className="text-xs font-medium text-slate-500">
                          {formatDate(doc.created_at)}
                        </span>
                      </div>

                      {/* Pipeline capability badges */}
                      {doc.status === 'ready' && (
                        <div className="flex items-center gap-1 mt-2.5 flex-wrap">
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-lg text-[9px] font-extrabold bg-orange-50 text-orange-600 border border-orange-200 shadow-sm select-none">
                            <Search className="w-2.5 h-2.5" />
                            BM25
                          </span>
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-lg text-[9px] font-extrabold bg-blue-50 text-blue-600 border border-blue-200 shadow-sm select-none">
                            ⚡ FAISS
                          </span>
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-lg text-[9px] font-extrabold bg-purple-50 text-purple-600 border border-purple-200 shadow-sm select-none">
                            <Eye className="w-2.5 h-2.5" />
                            CLIP
                          </span>
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-lg text-[9px] font-extrabold bg-amber-50 text-amber-600 border border-amber-200 shadow-sm select-none">
                            <Layout className="w-2.5 h-2.5" />
                            Layout
                          </span>
                        </div>
                      )}

                      {doc.status === 'failed' && doc.error_message && (
                        <p className="text-[11px] text-red-500 font-medium mt-1 select-none truncate">
                          Reason: {doc.error_message}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Inline Delete Button (always visible on hover or select) */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setDocumentToDelete(doc)
                    }}
                    className="flex-shrink-0 ml-2 p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all md:opacity-0 md:group-hover:opacity-100 active:scale-95"
                    title="Delete document"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Frosted glass Delete Confirmation Modal Overlay */}
      {documentToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-100 animate-scale-up">
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-4 text-red-600">
              <AlertCircle className="w-6 h-6 animate-pulse" />
            </div>
            <h4 className="text-base font-bold text-slate-950 mb-1">
              Delete Document permanently?
            </h4>
            <p className="text-xs text-slate-500 mb-6 leading-relaxed font-semibold">
              Are you sure you want to delete <span className="font-bold text-slate-800">{documentToDelete.filename}</span>? This will permanently erase all extracted neural text chunks, cropped figure matrices, visual embeddings, and dialog history.
            </p>
            
            <div className="flex space-x-2.5 justify-end">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setDocumentToDelete(null)}
                className="px-4 py-2 text-xs font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-lg shadow-sm transition-all cursor-pointer active:scale-95"
              >
                {isDeleting ? (
                  <Loader className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5" />
                )}
                <span>Delete</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}