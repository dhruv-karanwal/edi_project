'use client'

import { useState, useRef } from 'react'
import { Upload, FileText, CheckCircle, AlertCircle, Zap, Loader2 } from 'lucide-react'
import { uploadDocument } from '@/lib/api'
import ErrorAlert from './ErrorAlert'

interface UploadPanelProps {
  onUploadComplete: () => void
}

export default function UploadPanel({ onUploadComplete }: UploadPanelProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Drag & Drop Event Handlers ─────────────────────────────────────────────
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (isUploading) return

    const file = e.dataTransfer.files?.[0]
    if (file) {
      await processUpload(file)
    }
  }

  // ── File Selection Handler ───────────────────────────────────────────────
  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    await processUpload(file)
  }

  // ── Main Upload Process with Validation & Progress Tracking ──────────────
  const processUpload = async (file: File) => {
    // 1. File Type and Size Validation
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Unsupported File Format. Please upload a PDF document.')
      return
    }

    const maxSizeBytes = 50 * 1024 * 1024 // 50MB
    if (file.size > maxSizeBytes) {
      setError('File size exceeds the 50MB limit. Please upload a smaller document.')
      return
    }

    setIsUploading(true)
    setUploadProgress(0)
    setError(null)
    setSuccess(false)

    try {
      // 2. Perform upload with real-time Axios progress tracking
      await uploadDocument(file, (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        setUploadProgress(percentCompleted)
      })

      // 3. Update UI states upon successful completion
      setSuccess(true)
      onUploadComplete()

      // Reset file input element
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      // Automatically hide success indicator after 4 seconds
      setTimeout(() => setSuccess(false), 4000)
    } catch (err: any) {
      console.error('Document upload error:', err)
      const errorMsg = err.friendlyMessage || err.response?.data?.detail || 'Failed to upload document'
      setError(errorMsg)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="card-base p-6 shadow-medium card-hover border border-slate-100 bg-white">
      {/* Panel Header */}
      <div className="flex items-center space-x-2 mb-6">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-yellow-100 to-amber-100 flex items-center justify-center">
          <Zap className="w-4 h-4 text-yellow-600" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-slate-900">Upload Documents</h3>
          <p className="text-[10px] text-slate-500 font-medium">Add materials for neural ingestion</p>
        </div>
      </div>

      {/* Drag and Drop Zone Container */}
      <div
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 relative group overflow-hidden ${
          isUploading ? 'bg-slate-50/50 border-slate-300 cursor-not-allowed' :
          dragActive ? 'border-primary-500 bg-primary-50/50 scale-[0.98]' :
          'border-slate-300 hover:border-primary-400 hover:bg-slate-50 cursor-pointer'
        }`}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
          disabled={isUploading}
        />

        {isUploading ? (
          /* Upload In-Progress State */
          <div className="py-4 space-y-4">
            <div className="relative w-16 h-16 mx-auto flex items-center justify-center">
              <Loader2 className="w-12 h-12 text-primary-500 animate-spin absolute" />
              <FileText className="w-6 h-6 text-primary-400" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-800">Uploading Document...</p>
              <p className="text-xs text-slate-500 mt-1">Ingesting structures & running OCR pipeline</p>
            </div>
            
            {/* Real-time Progress Bar */}
            <div className="max-w-xs mx-auto space-y-1.5">
              <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-primary-500 h-full rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-slate-500 font-bold px-1">
                <span>{uploadProgress}%</span>
                <span>{uploadProgress < 100 ? 'Transferring...' : 'Extracting AI Regions...'}</span>
              </div>
            </div>
          </div>
        ) : success ? (
          /* Upload Success State */
          <div className="py-4 animate-fade-in space-y-2">
            <div className="w-12 h-12 bg-green-50 border border-green-200 rounded-full flex items-center justify-center mx-auto shadow-sm">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm font-extrabold text-green-700">Upload Successful!</p>
              <p className="text-xs text-green-500 mt-1 font-medium">
                Document is now being parsed by surya-ocr & CLIP
              </p>
            </div>
          </div>
        ) : (
          /* Normal Interactive Prompt State */
          <div className="space-y-4">
            <div className="w-14 h-14 bg-primary-50 border border-primary-100 rounded-full flex items-center justify-center mx-auto group-hover:scale-110 group-hover:bg-primary-100 transition-all duration-300 shadow-sm">
              <Upload className="w-6 h-6 text-primary-600" />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-bold text-slate-900">
                {dragActive ? 'Drop PDF here' : 'Click to select or drag PDF'}
              </p>
              <p className="text-[11px] text-slate-500">
                Native or scanned documents (up to 50MB)
              </p>
            </div>
            <div className="inline-flex px-3 py-1 bg-slate-100 rounded text-[10px] text-slate-500 font-bold border border-slate-200">
              PDF Document
            </div>
          </div>
        )}
      </div>

      {/* Error Alert Display */}
      {error && (
        <div className="mt-4 animate-slide-in">
          <ErrorAlert message={error} onClose={() => setError(null)} />
        </div>
      )}

      {/* Upload Help Banner */}
      <div className="mt-4 space-y-2.5 p-3 bg-slate-50 rounded-lg border border-slate-100 text-left">
        <p className="text-[11px] font-bold text-slate-700">Neural Intake Pipelines:</p>
        <div className="space-y-1.5">
          <div className="flex items-start gap-2 text-[10px] text-slate-600 font-medium">
            <div className="w-3.5 h-3.5 rounded bg-primary-100 text-primary-700 flex items-center justify-center text-[9px] font-extrabold flex-shrink-0 mt-0.5">
              1
            </div>
            <span>Adaptive OpenCV thresholding correct rotation & skew errors on scanned items.</span>
          </div>
          <div className="flex items-start gap-2 text-[10px] text-slate-600 font-medium">
            <div className="w-3.5 h-3.5 rounded bg-primary-100 text-primary-700 flex items-center justify-center text-[9px] font-extrabold flex-shrink-0 mt-0.5">
              2
            </div>
            <span>AI Layout model isolates figures, tables, formulas, and text zones separately.</span>
          </div>
          <div className="flex items-start gap-2 text-[10px] text-slate-600 font-medium">
            <div className="w-3.5 h-3.5 rounded bg-primary-100 text-primary-700 flex items-center justify-center text-[9px] font-extrabold flex-shrink-0 mt-0.5">
              3
            </div>
            <span>CLIP & BM25 map multimodal content into a high-dimensional hybrid search index.</span>
          </div>
        </div>
      </div>
    </div>
  )
}