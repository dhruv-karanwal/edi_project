import axios from 'axios'
import {
  Document,
  UploadResponse,
  QueryResponse,
  Conversation,
  DocumentConversationsResponse,
  Chunk,
  DocumentLayoutResponse,
} from '@/types'

//Centralized API base URL config. Production uses Render backend, fallback to localhost.
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

// Centralized Axios Instance with robust timeout and interceptor defaults
const api = axios.create({
  baseURL: API_URL.endsWith('/api') ? API_URL : `${API_URL}/api`,
  timeout: 360000, // 6 minutes maximum for deep neural calculations and document layout ingestion
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request Logger Interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} -> ${config.url}`, config.params || '')
    return config
  },
  (error) => {
    console.error('[API Request Error]', error)
    return Promise.reject(error)
  }
)

// Response Error Interceptor — Handles global failures, server offline, timeouts gracefully
api.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.status} <- ${response.config.url}`)
    return response
  },
  (error) => {
    const errorDetails = {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data,
      url: error.config?.url,
    }
    console.error('[API Response Error]', errorDetails)

    // Customize error message for user-facing UI elements
    if (error.code === 'ECONNABORTED') {
      error.friendlyMessage = 'The request timed out. The model calculation took longer than expected.'
    } else if (!error.response) {
      error.friendlyMessage = 'Unable to connect to the backend server. Please verify it is running on Render.'
    } else if (error.response.status === 500) {
      error.friendlyMessage = error.response.data?.detail || 'An unexpected internal server error occurred.'
    } else {
      error.friendlyMessage = error.response.data?.detail || 'An error occurred while processing the request.'
    }

    return Promise.reject(error)
  }
)

// ── Documents API ────────────────────────────────────────────────────────────

export const getDocuments = async (): Promise<Document[]> => {
  const response = await api.get('/documents')
  return response.data
}

export const getDocument = async (id: string): Promise<Document> => {
  const response = await api.get(`/documents/${id}`)
  return response.data
}

export const getDocumentChunks = async (
  id: string,
  params?: { chunk_type?: string; page?: number }
): Promise<Chunk[]> => {
  const response = await api.get(`/documents/${id}/chunks`, { params })
  return response.data
}

export const deleteDocument = async (id: string): Promise<void> => {
  await api.delete(`/documents/${id}`)
}

// ── v2.0 Layout Regions Overlay API ─────────────────────────────────────────

export const getDocumentLayout = async (id: string): Promise<DocumentLayoutResponse> => {
  const response = await api.get(`/documents/${id}/layout`)
  return response.data
}

// ── Upload API ────────────────────────────────────────────────────────────────

export const uploadDocument = async (
  file: File,
  onUploadProgress?: (progressEvent: any) => void
): Promise<UploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/ingest/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress, // Wire up Axios progress event for real-time progress bar
  })
  return response.data
}

export const getUploadStatus = async (documentId: string): Promise<Document> => {
  const response = await api.get(`/ingest/status/${documentId}`)
  return response.data
}

// ── Query & Chat API ──────────────────────────────────────────────────────────

export const askQuestion = async (
  documentId: string,
  question: string,
  conversationId?: string
): Promise<QueryResponse> => {
  const response = await api.post('/query/ask', {
    document_id: documentId,
    question,
    conversation_id: conversationId,
  })
  return response.data
}

export const getConversation = async (
  conversationId: string
): Promise<Conversation> => {
  const response = await api.get(`/query/conversations/${conversationId}`)
  return response.data
}

export const getLatestConversationForDocument = async (
  documentId: string
): Promise<Conversation> => {
  const response = await api.get(`/query/documents/${documentId}/latest-conversation`)
  return response.data
}

export const getDocumentConversations = async (
  documentId: string
): Promise<DocumentConversationsResponse> => {
  const response = await api.get(`/query/documents/${documentId}/conversations`)
  return response.data
}

// ── Helper to resolve Figure & Crop URLs ─────────────────────────────────────

export const getFigureUrl = (documentId: string, chunkId: string): string => {
  const base = API_URL.endsWith('/api') ? API_URL : `${API_URL}/api`
  return `${base}/documents/${documentId}/figure/${chunkId}`
}