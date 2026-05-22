'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Loader, User, Bot, Lightbulb, MessageSquarePlus, RefreshCw } from 'lucide-react'
import { Document, Message, Evidence, ConversationSummary } from '@/types'
import { askQuestion, getConversation, getDocumentConversations, getLatestConversationForDocument } from '@/lib/api'
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
  const [lastQuery, setLastQuery] = useState<string>('')
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const streamingTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Clear streaming timer on component unmount
  useEffect(() => {
    return () => {
      if (streamingTimerRef.current) {
        clearInterval(streamingTimerRef.current)
      }
    }
  }, [])

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
  }, [messages, isLoading])

  useEffect(() => {
    const loadConversation = async () => {
      if (streamingTimerRef.current) {
        clearInterval(streamingTimerRef.current)
      }
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
        // Ensure historical messages have timestamps
        const histMessages = conversation.messages.map((msg) => ({
          ...msg,
          created_at: msg.created_at || new Date().toISOString(),
        }))
        setMessages(histMessages)
        focusLatestAssistantMessage(histMessages)
      } catch (error) {
        console.error('Failed to load conversation history:', error)
      }
    }

    loadConversation()
  }, [document.id])

  const handleSelectConversation = async (nextConversationId: string) => {
    if (!nextConversationId) return
    if (streamingTimerRef.current) {
      clearInterval(streamingTimerRef.current)
    }

    setIsLoading(true)
    try {
      const conversation = await getConversation(nextConversationId)
      setConversationId(nextConversationId)
      const formattedMsgs = conversation.messages.map((m) => ({
        ...m,
        created_at: m.created_at || new Date().toISOString(),
      }))
      setMessages(formattedMsgs)
      focusLatestAssistantMessage(formattedMsgs)
    } catch (error) {
      console.error('Failed to load selected conversation:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    if (streamingTimerRef.current) {
      clearInterval(streamingTimerRef.current)
    }
    setConversationId(undefined)
    setMessages([])
    setInput('')
    setSelectedMessageIdx(null)
  }

  // ── Centralized Hybrid API Ingest & Simulated Word-by-Word Streaming ──
  const streamResponse = async (queryText: string, retryMode = false) => {
    setIsLoading(true)

    try {
      const response = await askQuestion(document.id, queryText, conversationId)

      // Update conversations history list
      if (!conversationId) {
        setConversationId(response.conversation_id)
        setConversations((prev) => [
          {
            conversation_id: response.conversation_id,
            created_at: new Date().toISOString(),
            last_message_at: new Date().toISOString(),
            message_count: retryMode ? prev[0]?.message_count || 2 : 2,
          },
          ...prev,
        ])
      } else {
        setConversations((prev) =>
          prev.map((conv) =>
            conv.conversation_id === response.conversation_id
              ? {
                  ...conv,
                  last_message_at: new Date().toISOString(),
                  message_count: conv.message_count + 2,
                }
              : conv
          )
        )
      }

      // Add empty assistant response to begin streaming
      const assistantMessage: Message = {
        role: 'assistant',
        content: '',
        evidence: response.evidence,
        created_at: new Date().toISOString(),
      }

      setMessages((prev) => {
        const updated = [...prev, assistantMessage]
        setSelectedMessageIdx(updated.length - 1)
        return updated
      })

      // Elegant streaming interval
      let currentText = ''
      const fullText = response.answer
      let charIdx = 0

      if (streamingTimerRef.current) {
        clearInterval(streamingTimerRef.current)
      }

      streamingTimerRef.current = setInterval(() => {
        if (charIdx < fullText.length) {
          // Increment text by blocks of 3 characters for responsive, high-speed rendering
          const chunk = fullText.slice(charIdx, charIdx + 3)
          currentText += chunk
          charIdx += 3

          setMessages((prev) => {
            const updated = [...prev]
            if (updated.length > 0) {
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: currentText,
              }
            }
            return updated
          })
        } else {
          if (streamingTimerRef.current) {
            clearInterval(streamingTimerRef.current)
          }

          // Set final exact text
          setMessages((prev) => {
            const updated = [...prev]
            if (updated.length > 0) {
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: fullText,
              }
            }
            return updated
          })

          onAnswerReceived({
            answer: response.answer,
            evidence: response.evidence,
          })
          setIsLoading(false)
        }
      }, 10)

    } catch (error: any) {
      console.error('Failed to get answer:', error)
      const errMsg = error.friendlyMessage || 'Sorry, I encountered an error processing your query. The backend service may be starting up on Render.'
      
      const errorMessage: Message = {
        role: 'assistant',
        content: errMsg,
        created_at: new Date().toISOString(),
      }
      
      // Inject error indicator safely
      Object.assign(errorMessage, { isError: true })

      setMessages((prev) => [...prev, errorMessage])
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const queryText = input.trim()
    setLastQuery(queryText)

    const userMessage: Message = {
      role: 'user',
      content: queryText,
      created_at: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')

    await streamResponse(queryText, false)
  }

  const handleRetry = async () => {
    if (!lastQuery.trim() || isLoading) return

    // Pop the failed error message first
    setMessages((prev) => {
      const updated = [...prev]
      if (updated.length > 0 && (updated[updated.length - 1] as any).isError) {
        updated.pop()
      }
      return updated
    })

    await streamResponse(lastQuery, true)
  }

  return (
    <div className="flex flex-col h-full bg-slate-50 border-r border-slate-200">
      {/* Top Header / History Selector */}
      <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-6 py-3 backdrop-blur-sm shadow-sm flex flex-col gap-2 sm:flex-row sm:items-center">
        <select
          value={conversationId || ''}
          onChange={(e) => handleSelectConversation(e.target.value)}
          aria-label="Conversation history"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 transition-all cursor-pointer"
        >
          <option value="">Current active draft</option>
          {conversations.map((conv) => (
            <option key={conv.conversation_id} value={conv.conversation_id}>
              {formatConversationLabel(conv)}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleNewChat}
          className="flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-semibold bg-white border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 hover:text-primary-600 transition-all shadow-sm active:scale-95"
        >
          <MessageSquarePlus className="w-4 h-4 text-primary-500" />
          <span>New chat</span>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 scrollbar-thin">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center py-10">
            <div className="text-center max-w-sm px-4">
              <div className="w-14 h-14 bg-gradient-to-tr from-primary-500 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-md shadow-primary-200 animate-pulse">
                <Bot className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-1">
                Advanced Neural Reader
              </h3>
              <p className="text-xs text-slate-500 mb-6 font-medium">
                Ask multi-modal questions about texts, layout regions, figures, and charts.
              </p>
              
              <div className="space-y-2 text-left">
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2 px-1">Suggested prompts:</p>
                <div className="space-y-2">
                  {[
                    'What are the main findings?',
                    'Explain the methodology used',
                    'Describe the core figures & tables',
                    'Summarize the results & equations',
                  ].map((example, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(example)}
                      className="block w-full px-4 py-2.5 text-xs text-left bg-white hover:bg-primary-50/50 rounded-xl transition-all border border-slate-200 hover:border-primary-300 font-semibold text-slate-600 hover:text-primary-700 shadow-sm"
                    >
                      <div className="flex items-center space-x-2">
                        <Lightbulb className="w-3.5 h-3.5 text-yellow-500 flex-shrink-0" />
                        <span className="truncate">{example}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, idx) => {
          const isUser = msg.role === 'user'
          const isError = (msg as any).isError
          
          return (
            <div
              key={idx}
              className={`flex items-start ${isUser ? 'justify-end' : 'justify-start'} animate-slide-in`}
            >
              {!isUser && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-tr from-primary-500 to-indigo-600 flex items-center justify-center mr-2.5 shadow-sm mt-0.5">
                  <Bot className="w-4.5 h-4.5 text-white" />
                </div>
              )}
              
              <div className="flex flex-col max-w-[85%] sm:max-w-[78%]">
                <div
                  className={`rounded-2xl px-4 py-3 shadow-sm border transition-all ${
                    isUser
                      ? 'bg-gradient-to-r from-primary-600 to-indigo-600 text-white rounded-tr-none border-transparent'
                      : isError
                      ? 'bg-red-50 text-red-900 border-red-200 rounded-tl-none'
                      : `bg-white text-slate-800 rounded-tl-none ${
                          selectedMessageIdx === idx
                            ? 'border-primary-500 ring-2 ring-primary-100 shadow-md shadow-primary-50/50'
                            : 'border-slate-200'
                        }`
                  }`}
                >
                  {!isUser ? (
                    <div className="prose-custom text-sm font-medium leading-relaxed break-words">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm font-semibold leading-relaxed break-words whitespace-pre-wrap">{msg.content}</p>
                  )}

                  {/* Evidence source pill */}
                  {!isUser && msg.evidence && msg.evidence.length > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedMessageIdx(idx)
                        onAnswerReceived({ answer: msg.content, evidence: msg.evidence || [] })
                      }}
                      className={`mt-2.5 inline-flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded-lg transition-all ${
                        selectedMessageIdx === idx
                          ? 'bg-primary-100 text-primary-700 font-extrabold shadow-sm'
                          : 'bg-slate-100 text-slate-600 hover:text-primary-700 hover:bg-primary-50'
                      }`}
                    >
                      <span>📎</span>
                      <span>{msg.evidence.length} ground{msg.evidence.length !== 1 ? 's' : ''} cited</span>
                    </button>
                  )}

                  {/* Timestamp inside/under the bubble */}
                  <span className={`text-[10px] mt-1.5 block select-none font-medium ${isUser ? 'text-indigo-200 text-right' : 'text-slate-400'}`}>
                    {new Date(msg.created_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                {/* Error Retry Option */}
                {isError && (
                  <div className="mt-2 self-start flex items-center">
                    <button
                      type="button"
                      onClick={handleRetry}
                      className="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 bg-white text-red-600 hover:bg-red-50 hover:text-red-700 rounded-lg border border-red-200 shadow-sm transition-all active:scale-95"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Retry prompt</span>
                    </button>
                  </div>
                )}
              </div>

              {isUser && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center ml-2.5 shadow-sm mt-0.5">
                  <User className="w-4.5 h-4.5 text-slate-600" />
                </div>
              )}
            </div>
          )
        })}

        {/* Bouncing Dots typing animation */}
        {isLoading && messages.length > 0 && messages[messages.length - 1].role === 'user' && (
          <div className="flex items-start justify-start animate-slide-in">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-tr from-primary-500 to-indigo-600 flex items-center justify-center mr-2.5 shadow-sm mt-0.5">
              <Bot className="w-4.5 h-4.5 text-white" />
            </div>
            <div className="bg-white rounded-2xl rounded-tl-none px-4 py-3.5 border border-slate-200 shadow-sm flex items-center justify-center">
              <div className="flex items-center space-x-1.5 py-1 px-1">
                <span className="w-2.5 h-2.5 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                <span className="w-2.5 h-2.5 bg-primary-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 p-4 sm:p-5 bg-white">
        <form onSubmit={handleSubmit} className="flex space-x-2 sm:space-x-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about this research document..."
            disabled={isLoading}
            className="flex-1 px-4 py-3 bg-slate-50 border border-slate-300 rounded-xl focus:bg-white text-slate-800 text-sm font-semibold placeholder-slate-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 transition-all disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-3 bg-gradient-to-r from-primary-600 to-indigo-600 hover:from-primary-700 hover:to-indigo-700 text-white rounded-xl font-bold text-sm transition-all shadow-md hover:shadow-primary-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5 hover:scale-[1.02] active:scale-95 flex-shrink-0"
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