'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Loader, User, Bot, Lightbulb, MessageSquarePlus } from 'lucide-react'
import { Document, Message, Evidence, ConversationSummary } from '@/types'
import { askQuestion, getConversation, getDocumentConversations, getLatestConversationForDocument } from '@/lib/api'
import LoadingSpinner from './LoadingSpinner'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ChatPanelProps {
  document: Document
  onAnswerReceived: (answer: { answer: string; evidence: Evidence[] }) => void
}

export default function ChatPanel({ document, onAnswerReceived }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | undefined>()
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [selectedMessageIdx, setSelectedMessageIdx] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const formatConversationLabel = (conversation: ConversationSummary) => {
    const timestamp = conversation.last_message_at || conversation.created_at
    const date = new Date(timestamp)
    const prettyTime = date.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
    const turns = Math.floor(conversation.message_count / 2)
    const turnLabel = turns === 1 ? '1 turn' : `${turns} turns`
    return `${prettyTime} (${turnLabel})`
  }

  const focusLatestAssistantMessage = (conversationMessages: Message[]) => {
    const selectedIdx = (() => {
      for (let i = conversationMessages.length - 1; i >= 0; i -= 1) {
        const msg = conversationMessages[i]
        if (msg.role === 'assistant' && msg.evidence && msg.evidence.length) {
          return i
        }
      }
      return null
    })()

    if (selectedIdx !== null) {
      const selectedMessage = conversationMessages[selectedIdx]
      setSelectedMessageIdx(selectedIdx)
      onAnswerReceived({
        answer: selectedMessage.content,
        evidence: selectedMessage.evidence || [],
      })
    } else {
      setSelectedMessageIdx(null)
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    const loadConversation = async () => {
      setMessages([])
      setConversationId(undefined)
      setConversations([])
      setSelectedMessageIdx(null)
      setInput('')
      setIsLoading(false)

      try {
        const conversationList = await getDocumentConversations(document.id)
        setConversations(conversationList.conversations)

        const conversation = await getLatestConversationForDocument(document.id)
        if (!conversation.conversation_id || !conversation.messages.length) {
          return
        }

        setConversationId(conversation.conversation_id)
        setMessages(conversation.messages)
        focusLatestAssistantMessage(conversation.messages)
      } catch (error) {
        console.error('Failed to load conversation history:', error)
      }
    }

    loadConversation()
  }, [document.id])

  const handleSelectConversation = async (nextConversationId: string) => {
    if (!nextConversationId) return

    setIsLoading(true)
    try {
      const conversation = await getConversation(nextConversationId)
      setConversationId(nextConversationId)
      setMessages(conversation.messages)
      focusLatestAssistantMessage(conversation.messages)
    } catch (error) {
      console.error('Failed to load selected conversation:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    setConversationId(undefined)
    setMessages([])
    setInput('')
    setSelectedMessageIdx(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      role: 'user',
      content: input,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await askQuestion(document.id, input, conversationId)
      
      if (!conversationId) {
        setConversationId(response.conversation_id)
        setConversations((prev) => [
          {
            conversation_id: response.conversation_id,
            created_at: new Date().toISOString(),
            last_message_at: new Date().toISOString(),
            message_count: 2,
          },
          ...prev,
        ])
      } else {
        setConversations((prev) =>
          prev.map((conversation) =>
            conversation.conversation_id === response.conversation_id
              ? {
                  ...conversation,
                  last_message_at: new Date().toISOString(),
                  message_count: conversation.message_count + 2,
                }
              : conversation
          )
        )
      }

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.answer,
        evidence: response.evidence,
      }

      setMessages((prev) => {
        const updated = [...prev, assistantMessage]
        setSelectedMessageIdx(updated.length - 1)
        return updated
      })
      onAnswerReceived({
        answer: response.answer,
        evidence: response.evidence,
      })
    } catch (error) {
      console.error('Failed to get answer:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your question. Please try again.',
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin">
        <div className="sticky top-0 z-10 -mx-6 border-b border-slate-100 bg-white/90 px-6 pb-3 pt-1 backdrop-blur-sm">
          <div className="flex items-center gap-2">
          <select
            value={conversationId || ''}
            onChange={(e) => handleSelectConversation(e.target.value)}
            aria-label="Conversation history"
            className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700"
          >
            <option value="">Current draft chat</option>
            {conversations.map((conversation) => (
              <option key={conversation.conversation_id} value={conversation.conversation_id}>
                {formatConversationLabel(conversation)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleNewChat}
            className="btn-secondary whitespace-nowrap px-3 py-2"
          >
            <MessageSquarePlus className="w-4 h-4" />
            New chat
          </button>
          </div>
        </div>

        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center max-w-sm">
              <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Bot className="w-8 h-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-2">
                Ask me anything
              </h3>
              <p className="text-sm text-slate-600 mb-6">
                I can help with text, figures, tables, equations, and more
              </p>
              
              <div className="space-y-2">
                <p className="text-xs font-bold text-slate-700 mb-3">Example questions:</p>
                <div className="space-y-2">
                  {[
                    'What are the main findings?',
                    'Explain the methodology',
                    'Describe Figure 1',
                    'Summarize the results',
                  ].map((example, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(example)}
                      className="block w-full px-4 py-2.5 text-sm text-left bg-gradient-to-r from-slate-50 to-slate-50 hover:from-primary-50 hover:to-primary-50 rounded-lg transition-all border border-slate-200 hover:border-primary-300 font-medium text-slate-700 hover:text-primary-700"
                    >
                      <div className="flex items-center space-x-2">
                        <Lightbulb className="w-3.5 h-3.5 text-yellow-500" />
                        <span>{example}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-in transition-all duration-200 ${
              msg.role === 'assistant' && selectedMessageIdx === idx ? 'opacity-100' : ''
            }`}
          >
            {msg.role === 'assistant' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center mr-3">
                <Bot className="w-4 h-4 text-primary-600" />
              </div>
            )}
            
            <div
              className={`max-w-[82%] rounded-2xl px-4 py-3 transition-all lg:max-w-[78%] xl:max-w-[74%] ${
                msg.role === 'user'
                  ? 'bg-primary-500 text-white rounded-br-none'
                  : `bg-slate-100 text-slate-900 rounded-bl-none border-2 ${
                      selectedMessageIdx === idx
                        ? 'border-primary-500 shadow-lg ring-2 ring-primary-200'
                        : 'border-slate-200'
                    }`
              }`}
            >
              {msg.role === 'assistant' ? (
                <div className="prose-custom">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm font-medium">{msg.content}</p>
              )}

              {msg.role === 'assistant' && msg.evidence && msg.evidence.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedMessageIdx(idx)
                    onAnswerReceived({ answer: msg.content, evidence: msg.evidence || [] })
                  }}
                  className={`mt-3 block text-xs font-semibold px-2 py-1 rounded transition-all ${
                    selectedMessageIdx === idx
                      ? 'bg-primary-100 text-primary-700 font-bold'
                      : 'text-primary-600 hover:text-primary-700 hover:bg-primary-50'
                  }`}
                >
                  📎 {msg.evidence.length} evidence source{msg.evidence.length !== 1 ? 's' : ''}
                </button>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-300 flex items-center justify-center ml-3">
                <User className="w-4 h-4 text-slate-700" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start animate-slide-in">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center mr-3">
              <Bot className="w-4 h-4 text-primary-600" />
            </div>
            <div className="bg-slate-100 text-slate-900 rounded-lg rounded-bl-none px-4 py-3 border border-slate-200">
              <LoadingSpinner size="sm" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-100 p-6 bg-slate-50">
        <form onSubmit={handleSubmit} className="flex space-x-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about the document..."
            disabled={isLoading}
            className="flex-1 px-4 py-3 bg-white border border-slate-300 rounded-lg input-focus disabled:opacity-50 text-sm font-medium"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-3 bg-gradient-primary text-white rounded-lg font-medium transition-all hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105 active:scale-95 flex items-center space-x-2"
          >
            {isLoading ? (
              <Loader className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">Send</span>
          </button>
        </form>
      </div>
    </div>
  )
}