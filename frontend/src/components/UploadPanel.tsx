'use client'

import { useState, useRef } from 'react'
import { Upload, FileText, CheckCircle, AlertCircle, Zap } from 'lucide-react'
import { uploadDocument } from '@/lib/api'
import LoadingSpinner from './LoadingSpinner'
import ErrorAlert from './ErrorAlert'

interface UploadPanelProps {
  onUploadComplete: () => void
}

export default function UploadPanel({ onUploadComplete }: UploadPanelProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.pdf')) {
      setError('Please select a PDF file')
      return
    }

    setIsUploading(true)
    setError(null)
    setSuccess(false)

    try {
      await uploadDocument(file)
      setSuccess(true)
      onUploadComplete()
      
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload document')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="card-base p-6 shadow-medium card-hover">
      <div className="flex items-center space-x-2 mb-6">
        <Zap className="w-5 h-5 text-yellow-500" />
        <h3 className="text-lg font-bold bg-gradient-to-r from-slate-900 to-slate-700 bg-clip-text text-transparent">
          Upload Documents
        </h3>
      </div>
      
      <div
        className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-primary-400 hover:bg-primary-50/50 transition-all cursor-pointer group"
        onClick={() => fileInputRef.current?.click()}
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
          <div className="py-4">
            <LoadingSpinner size="lg" />
            <p className="text-sm text-slate-600 mt-3 font-medium">Processing PDF...</p>
            <p className="text-xs text-slate-500 mt-1">This may take a moment for large documents</p>
          </div>
        ) : success ? (
          <div className="py-4 animate-fade-in">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <p className="text-sm font-bold text-green-700">Upload successful!</p>
            <p className="text-xs text-green-600 mt-1">Your document is now being processed</p>
          </div>
        ) : (
          <>
            <div className="w-14 h-14 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:bg-primary-200 transition-colors">
              <Upload className="w-7 h-7 text-primary-600" />
            </div>
            <p className="text-sm font-bold text-slate-900 mb-1">
              Click to upload PDF
            </p>
            <p className="text-xs text-slate-500 mb-3">
              Research papers, articles, reports
            </p>
            <p className="text-xs text-slate-400 font-medium">
              Or drag and drop (max 50MB)
            </p>
          </>
        )}
      </div>

      {error && (
        <div className="mt-4 animate-slide-in">
          <ErrorAlert message={error} onClose={() => setError(null)} />
        </div>
      )}

      <div className="mt-4 space-y-2 p-3 bg-slate-50 rounded-lg border border-slate-100">
        <p className="text-xs font-bold text-slate-700">Features:</p>
        <div className="space-y-1">
          <p className="text-xs text-slate-600 flex items-start space-x-2">
            <span className="text-primary-600 font-bold mt-0.5">•</span>
            <span>PDF support with automatic text extraction</span>
          </p>
          <p className="text-xs text-slate-600 flex items-start space-x-2">
            <span className="text-primary-600 font-bold mt-0.5">•</span>
            <span>OCR processing for scanned documents</span>
          </p>
          <p className="text-xs text-slate-600 flex items-start space-x-2">
            <span className="text-primary-600 font-bold mt-0.5">•</span>
            <span>Automatic figure, table & equation detection</span>
          </p>
        </div>
      </div>
    </div>
  )
}