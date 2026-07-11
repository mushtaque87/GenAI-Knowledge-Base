export interface OTelSpan {
  name: string;
  durationMs: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  isStreaming?: boolean;
  spans?: OTelSpan[];
  timestamp: string;
}

export interface SearchLogItem {
  query: string;
  answer: string;
  sources: string[];
  timestamp: string;
  totalDurationMs: number;
}
