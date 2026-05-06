import { AlertCircle, X } from 'lucide-react'

interface ErrorAlertProps {
  message: string
  onClose: () => void
}

export default function ErrorAlert({ message, onClose }: ErrorAlertProps) {
  return (
    <div className="bg-gradient-to-r from-red-50 to-red-50 border-2 border-red-200 rounded-lg p-4 flex items-start space-x-3 shadow-soft animate-slide-in">
      <div className="flex-shrink-0 p-2 bg-red-100 rounded-lg mt-0.5">
        <AlertCircle className="w-5 h-5 text-red-600" />
      </div>
      <div className="flex-1">
        <p className="text-sm font-medium text-red-900">{message}</p>
      </div>
      <button
        onClick={onClose}
        className="flex-shrink-0 p-1 text-red-500 hover:text-red-700 hover:bg-red-100 rounded-lg transition-all"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}