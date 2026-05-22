export interface Document {
  id: string
  filename: string
  status: 'pending' | 'processing' | 'ready' | 'failed'
  page_count: number | null
  created_at: string
  error_message?: string | null
}

export interface Chunk {
  id: string
  chunk_type: 'text' | 'figure' | 'table' | 'equation' | 'caption'
  content: string
  page_number: number
  section_title: string | null
  caption: string | null
  image_path: string | null
  bbox: BoundingBox | null
  // v2.0 — AI layout detection
  layout_label?: string | null
  layout_confidence?: number | null
}

export interface BoundingBox {
  x0: number
  y0: number
  x1: number
  y1: number
}

export interface Evidence {
  chunk_id: string
  chunk_type: string
  page_number: number
  section_title: string | null
  snippet: string
  image_url: string | null
  relevance_score: number
  // v2.0 — Hybrid retrieval metadata
  retrieval_source?: string | null  // "bm25" | "semantic" | "visual" | "multimodal" | "hybrid"
  layout_label?: string | null      // surya region label
  bm25_score?: number | null
  faiss_score?: number | null
  clip_score?: number | null
}

export interface QueryResponse {
  answer: string
  conversation_id: string
  evidence: Evidence[]
}

export interface UploadResponse {
  document_id: string
  filename: string
  status: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  evidence?: Evidence[]
  created_at?: string
}

export interface Conversation {
  conversation_id: string | null
  document_id: string
  messages: Message[]
}

export interface ConversationSummary {
  conversation_id: string
  created_at: string
  message_count: number
  last_message_at: string | null
}

export interface DocumentConversationsResponse {
  document_id: string
  conversations: ConversationSummary[]
}

// v2.0 — Layout overlay types
export interface LayoutRegion {
  chunk_id: string
  chunk_type: string
  layout_label: string | null
  layout_confidence: number | null
  page_number: number
  bbox: BoundingBox | null
  content_preview: string
}

export interface DocumentLayoutResponse {
  document_id: string
  regions: LayoutRegion[]
  total_count: number
}