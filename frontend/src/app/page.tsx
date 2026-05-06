'use client'

import { useState, useEffect } from 'react'
import { FileText, MessageSquare, Database, Sparkles, ShieldCheck, BarChart3 } from 'lucide-react'
import UploadPanel from '@/components/UploadPanel'
import DocumentList from '@/components/DocumentList'
import ChatPanel from '@/components/ChatPanel'
import EvidencePane from '@/components/EvidencePane'
import { Document, Evidence } from '@/types'
import { getDocuments } from '@/lib/api'

interface SelectedAnswer {
  answer: string
  evidence: Evidence[]
}

export default function Home() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null)
  const [currentAnswer, setCurrentAnswer] = useState<SelectedAnswer | null>(null)

  useEffect(() => {
    loadDocuments()
    const interval = setInterval(loadDocuments, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [])

  const loadDocuments = async () => {
    try {
      const docs = await getDocuments()
      setDocuments(docs)
    } catch (error) {
      console.error('Failed to load documents:', error)
    }
  }

  const handleDocumentUploaded = () => {
    loadDocuments()
  }

  const handleDocumentSelected = (doc: Document) => {
    setSelectedDocument(doc)
    setCurrentAnswer(null)
  }

  const handleAnswerReceived = (answer: SelectedAnswer) => {
    setCurrentAnswer(answer)
  }

  return (
    <div className="app-shell">
      <header className="glass-header">
        <div className="mx-auto flex max-w-[1760px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-cyan-500 text-white shadow-lg shadow-sky-500/30">
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-display text-xl font-bold sm:text-2xl">
                Research RAG
              </h1>
              <p className="text-xs font-medium text-slate-500">Document Intelligence Workspace</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="badge-base border border-slate-200 bg-white text-slate-700">
              <Database className="h-3.5 w-3.5" />
              {documents.length} documents
            </div>
            <div className="badge-base border border-emerald-200 bg-emerald-50 text-emerald-700">
              <ShieldCheck className="h-3.5 w-3.5" />
              Production ready
            </div>
            <div className="badge-base border border-sky-200 bg-sky-50 text-sky-700">
              <BarChart3 className="h-3.5 w-3.5" />
              Multimodal RAG
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1760px] px-4 py-4 sm:px-6 sm:py-6">
        <section className="mb-4 rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-sm sm:mb-6 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="panel-title">Workspace Overview</p>
              <p className="mt-1 text-sm text-slate-600">
                Upload PDFs, run grounded chat, and inspect evidence without switching contexts.
              </p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
              <Sparkles className="h-4 w-4 text-amber-500" />
              {selectedDocument ? `Active: ${selectedDocument.filename}` : 'Select a document to begin'}
            </div>
          </div>
        </section>

        <div className="grid gap-4 xl:grid-cols-12 xl:gap-6">
          <aside className="order-2 space-y-4 xl:order-1 xl:col-span-3 xl:h-[calc(100vh-255px)] xl:overflow-y-auto scrollbar-thin">
            <UploadPanel onUploadComplete={handleDocumentUploaded} />
            <DocumentList
              documents={documents}
              selectedDocument={selectedDocument}
              onSelectDocument={handleDocumentSelected}
            />
          </aside>

          <section className="order-1 xl:order-2 xl:col-span-6">
            {selectedDocument ? (
              <div className="card-base h-[calc(100vh-255px)] overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
                  <div>
                    <p className="panel-title">Assistant</p>
                    <p className="mt-1 text-sm font-semibold text-slate-800">
                      Analyzing {selectedDocument.filename}
                    </p>
                  </div>
                  <div className="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
                    <MessageSquare className="h-3.5 w-3.5" />
                    Live chat
                  </div>
                </div>
                <ChatPanel
                  document={selectedDocument}
                  onAnswerReceived={handleAnswerReceived}
                />
              </div>
            ) : (
              <div className="card-base flex h-[420px] items-center justify-center xl:h-[calc(100vh-255px)]">
                <div className="text-center">
                  <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-xl bg-sky-100">
                    <MessageSquare className="w-8 h-8 text-primary-500" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900">Select a document</h3>
                  <p className="mt-1 text-sm text-slate-500">Upload or choose a document to start grounded chat</p>
                </div>
              </div>
            )}
          </section>

          <aside className="order-3 xl:col-span-3 xl:h-[calc(100vh-255px)] xl:overflow-y-auto scrollbar-thin">
            {currentAnswer?.evidence?.length ? (
              <EvidencePane evidence={currentAnswer.evidence} />
            ) : (
              <div className="card-base min-h-[280px] p-6 xl:h-[calc(100vh-255px)]">
                <p className="panel-title">Evidence</p>
                <div className="mt-8 text-center text-slate-500">
                  <Sparkles className="mx-auto mb-3 h-10 w-10 text-slate-300" />
                  <p className="text-base font-semibold text-slate-900">No evidence selected</p>
                  <p className="mt-1 text-sm">Choose a response badge in chat to inspect sources</p>
                </div>
              </div>
            )}
          </aside>
        </div>
      </main>
    </div>
  )
}