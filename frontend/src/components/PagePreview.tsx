'use client'

import { useState } from 'react'
import { ZoomIn, ZoomOut, X, Download, Copy } from 'lucide-react'

interface PagePreviewProps {
  imageUrl: string
  pageNumber: number
  onClose: () => void
}

export default function PagePreview({ imageUrl, pageNumber, onClose }: PagePreviewProps) {
  const [zoom, setZoom] = useState(100)
  const [downloaded, setDownloaded] = useState(false)

  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = imageUrl
    link.download = `page-${pageNumber}.png`
    link.click()
    setDownloaded(true)
    setTimeout(() => setDownloaded(false), 2000)
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className="bg-white rounded-2xl shadow-xl max-w-4xl max-h-[90vh] w-full flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-transparent">
          <div>
            <h3 className="text-lg font-bold text-slate-900">
              Page {pageNumber}
            </h3>
            <p className="text-xs text-slate-500 font-medium">Document preview</p>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setZoom(Math.max(50, zoom - 10))}
              className="p-2 hover:bg-primary-100 text-primary-600 rounded-lg transition-all hover:scale-110 active:scale-95"
              title="Zoom out"
            >
              <ZoomOut className="w-5 h-5" />
            </button>
            <span className="text-sm font-bold text-slate-700 w-14 text-center bg-primary-50 px-2 py-1 rounded-lg border border-primary-200">
              {zoom}%
            </span>
            <button
              onClick={() => setZoom(Math.min(200, zoom + 10))}
              className="p-2 hover:bg-primary-100 text-primary-600 rounded-lg transition-all hover:scale-110 active:scale-95"
              title="Zoom in"
            >
              <ZoomIn className="w-5 h-5" />
            </button>
            
            <div className="w-px h-6 bg-slate-200 mx-2"></div>

            <button
              onClick={handleDownload}
              className="p-2 hover:bg-slate-100 text-slate-600 rounded-lg transition-all hover:text-primary-600"
              title="Download"
            >
              <Download className="w-5 h-5" />
            </button>

            <button
              onClick={onClose}
              className="p-2 hover:bg-red-100 text-slate-600 hover:text-red-600 rounded-lg transition-all"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Image Container */}
        <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-100 to-slate-50">
          <div className="flex items-center justify-center min-h-full p-6">
            <div className="bg-white rounded-lg shadow-lg border border-slate-200 overflow-hidden">
              <img
                src={imageUrl}
                alt={`Page ${pageNumber}`}
                style={{ width: `${zoom}%` }}
                className="max-w-none"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}