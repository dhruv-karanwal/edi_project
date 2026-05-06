import axios from 'axios'
import {
  Document,
  UploadResponse,
  QueryResponse,
  Conversation,
  DocumentConversationsResponse,
  Chunk,
} from '@/types'

const API_URL = 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_URL,
  timeout: 360000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Documents
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

// Upload
export const uploadDocument = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/ingest/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export const getUploadStatus = async (documentId: string): Promise<Document> => {
  const response = await api.get(`/ingest/status/${documentId}`)
  return response.data
}

// Query
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

// Helper to get figure URL
export const getFigureUrl = (documentId: string, chunkId: string): string => {
  return `${API_URL}/documents/${documentId}/figure/${chunkId}`
}