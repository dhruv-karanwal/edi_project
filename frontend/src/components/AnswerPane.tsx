'use client'

import { Lightbulb, Copy, Check } from 'lucide-react'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface AnswerPaneProps {
  answer: string
}

export default function AnswerPane({ answer }: AnswerPaneProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(answer)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="card-base p-6 shadow-medium overflow-hidden">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-to-br from-yellow-100 to-amber-100 rounded-lg flex items-center justify-center">
            <Lightbulb className="w-5 h-5 text-yellow-600" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">Answer</h3>
            <p className="text-xs text-slate-500 font-medium">AI-generated response</p>
          </div>
        </div>
        <button
          onClick={handleCopy}
          className="p-2 hover:bg-slate-100 rounded-lg transition-colors text-slate-600 hover:text-primary-600"
          title="Copy answer"
        >
          {copied ? (
            <Check className="w-5 h-5 text-green-500" />
          ) : (
            <Copy className="w-5 h-5" />
          )}
        </button>
      </div>
      
      <div className="prose-custom text-slate-700 leading-relaxed">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ node, ...props }) => <p className="mb-3 text-sm" {...props} />,
            strong: ({ node, ...props }) => <strong className="font-bold text-slate-900" {...props} />,
            em: ({ node, ...props }) => <em className="italic text-slate-700" {...props} />,
            ul: ({ node, ...props }) => <ul className="list-disc list-inside space-y-2 mb-3" {...props} />,
            ol: ({ node, ...props }) => <ol className="list-decimal list-inside space-y-2 mb-3" {...props} />,
            li: ({ node, ...props }) => <li className="text-sm" {...props} />,
            a: ({ node, ...props }) => (
              <a className="text-primary-600 hover:text-primary-700 font-medium underline" {...props} />
            ),
          }}
        >
          {answer}
        </ReactMarkdown>
      </div>
    </div>
  )
}