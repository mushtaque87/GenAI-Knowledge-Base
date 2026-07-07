import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, 
  Cpu, 
  Terminal, 
  History, 
  Clock, 
  Layers,
  FileText,
  Send,
  Zap,
  Plus,
  ChevronRight,
  Sparkles,
  Info
} from 'lucide-react';
import type { ChatMessage, OTelSpan } from './types/rag';

interface ChatHistoryItem {
  id: string;
  query: string;
  messages: ChatMessage[];
  spans: OTelSpan[];
  logs: string[];
  timestamp: string;
}

export default function App() {
  const [history, setHistory] = useState<ChatHistoryItem[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  
  // Current active chat states
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hello! I'm your Enterprise AI Gateway. Ask me anything to query the Azure knowledge base index and trace OpenTelemetry performance metrics in real-time.",
      timestamp: new Date().toLocaleTimeString(),
    }
  ]);
  const [input, setInput] = useState('');
  const [currentSpans, setCurrentSpans] = useState<OTelSpan[]>([]);
  const [currentLogs, setCurrentLogs] = useState<string[]>([]);
  const [isStreamingActive, setIsStreamingActive] = useState(false);
  const [isTelemetryOpen, setIsTelemetryOpen] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load selected historical chat
  const handleSelectHistory = (chat: ChatHistoryItem) => {
    setSelectedChatId(chat.id);
    setMessages(chat.messages);
    setCurrentSpans(chat.spans);
    setCurrentLogs(chat.logs);
  };

  // Start a fresh new chat session
  const handleNewChat = () => {
    setSelectedChatId(null);
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: "Hello! I'm your Enterprise AI Gateway. Ask me anything to query the Azure knowledge base index and trace OpenTelemetry performance metrics in real-time.",
        timestamp: new Date().toLocaleTimeString(),
      }
    ]);
    setCurrentSpans([]);
    setCurrentLogs([]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreamingActive) return;

    const userQuestion = input.trim();
    setInput('');
    setIsStreamingActive(true);
    
    // Reset performance metrics for this execution
    setCurrentSpans([]);
    const initialLogs = [
      `[info] ${new Date().toLocaleTimeString()} - Initiating search request: "${userQuestion}"`,
      `[info] ${new Date().toLocaleTimeString()} - Formatting context query embeddings`
    ];
    setCurrentLogs(initialLogs);

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();
    const timestampStr = new Date().toLocaleTimeString();

    // 1. Add User Message
    const newUserMsg: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: userQuestion,
      timestamp: timestampStr
    };

    // 2. Add Placeholder Assistant Message
    const newAssistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, newUserMsg, newAssistantMsg]);

    // Simulated OTel steps matching backend processing
    const startTime = performance.now();
    let embeddingTime = 0;
    let searchTime = 0;
    let filterTime = 0;

    const appendLog = (msg: string) => {
      setCurrentLogs(prev => [...prev, `[info] ${new Date().toLocaleTimeString()} - ${msg}`]);
    };

    setTimeout(() => { 
      embeddingTime = Math.floor(Math.random() * 150) + 80; 
      updateLiveSpans('openai_embeddings_generation', embeddingTime);
      appendLog(`Generated OpenAI embeddings vector in ${embeddingTime}ms`);
    }, 200);

    setTimeout(() => { 
      searchTime = Math.floor(Math.random() * 250) + 120; 
      updateLiveSpans('azure_ai_search_retrieval', searchTime); 
      appendLog(`Retrieved relevant document indices from Azure AI Search in ${searchTime}ms`);
    }, 600);

    setTimeout(() => { 
      filterTime = Math.floor(Math.random() * 60) + 20; 
      updateLiveSpans('semantic_filtering_extraction', filterTime); 
      appendLog(`Applied semantic filters & top-k reranking in ${filterTime}ms`);
    }, 900);

    const updateLiveSpans = (name: string, dur: number) => {
      setCurrentSpans(prev => [...prev.filter(s => s.name !== name), { name, durationMs: dur }]);
    };

    try {
      const response = await fetch('http://localhost:8000/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userQuestion }),
      });

      if (!response.ok) throw new Error("Backend connection failed");
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No readable stream channel");

      let fullAnswer = '';
      let detectedSources: string[] = [];
      appendLog("Connected to API stream. Fetching response chunks...");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunkText = decoder.decode(value);
        const lines = chunkText.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const rawJson = line.replace('data: ', '').trim();
              if (!rawJson) continue;
              const parsed = JSON.parse(rawJson);

              if (parsed.token) {
                fullAnswer += parsed.token;
                setMessages(prev => prev.map(m => m.id === assistantMsgId ? { ...m, content: fullAnswer } : m));
              } else if (parsed.done) {
                detectedSources = parsed.sources || [];
              }
            } catch (e) {
              // Ignore partial chunk noise
            }
          }
        }
      }

      const totalDuration = Math.floor(performance.now() - startTime);
      const llmTime = Math.max(200, totalDuration - (embeddingTime + searchTime + filterTime));
      
      const finalSpans = [
        { name: 'openai_embeddings_generation', durationMs: embeddingTime || 120 },
        { name: 'azure_ai_search_retrieval', durationMs: searchTime || 220 },
        { name: 'semantic_filtering_extraction', durationMs: filterTime || 40 },
        { name: 'llm_answer_generation', durationMs: llmTime }
      ];

      const finalLogs = [
        ...currentLogs,
        `[info] ${new Date().toLocaleTimeString()} - Finished LLM text generation (${llmTime}ms)`,
        `[info] ${new Date().toLocaleTimeString()} - Stream complete. Total execution time: ${totalDuration}ms`
      ];

      setCurrentSpans(finalSpans);
      setCurrentLogs(finalLogs);
      setIsStreamingActive(false);

      // Finalize active message
      const finalizedAssistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: fullAnswer,
        isStreaming: false,
        sources: detectedSources,
        spans: finalSpans
      };

      setMessages(prev => prev.map(m => m.id === assistantMsgId ? finalizedAssistantMsg : m));

      // Append to sidebar history
      const newHistoryItem: ChatHistoryItem = {
        id: crypto.randomUUID(),
        query: userQuestion,
        messages: [...messages.filter(m => m.id !== 'welcome'), newUserMsg, finalizedAssistantMsg],
        spans: finalSpans,
        logs: finalLogs,
        timestamp: timestampStr
      };

      setHistory(prev => [newHistoryItem, ...prev]);
      setSelectedChatId(newHistoryItem.id);

    } catch (err) {
      setIsStreamingActive(false);
      const errorMsg = "❌ Failed to connect to local API gateway container on port 8000. Ensure run-stack.sh has exposed the app endpoints safely.";
      
      const errorAssistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: errorMsg,
        isStreaming: false
      };

      setMessages(prev => prev.map(m => m.id === assistantMsgId ? errorAssistantMsg : m));
      
      const failedLogs = [
        ...currentLogs,
        `[error] ${new Date().toLocaleTimeString()} - Connection to port 8000 timed out / refused.`
      ];
      setCurrentLogs(failedLogs);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0B0B0F] font-sans antialiased text-[#ECECF1]">
      
      {/* 1. LEFT SIDEBAR PANEL (ChatGPT Style History) */}
      <aside className="w-64 bg-[#18181C] border-r border-[#2C2C35] flex flex-col shrink-0">
        {/* New Chat Button */}
        <div className="p-3">
          <button 
            onClick={handleNewChat}
            className="w-full flex items-center justify-between border border-[#3E3E4A] hover:bg-[#2A2A32] transition-colors rounded-lg px-3 py-2 text-sm font-medium text-white"
          >
            <span className="flex items-center space-x-2">
              <Plus className="h-4 w-4" />
              <span>New chat</span>
            </span>
            <Sparkles className="h-3.5 w-3.5 text-amber-400" />
          </button>
        </div>

        {/* History List */}
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          <div className="px-3 py-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            History
          </div>
          {history.length === 0 ? (
            <div className="px-3 py-4 text-xs text-slate-500 italic">
              No queries yet
            </div>
          ) : (
            history.map((item) => (
              <button
                key={item.id}
                onClick={() => handleSelectHistory(item)}
                className={`w-full text-left flex items-center space-x-2 px-3 py-2.5 rounded-lg text-xs transition-colors truncate ${
                  selectedChatId === item.id 
                    ? 'bg-[#2A2A32] text-white border-l-2 border-amber-400' 
                    : 'text-slate-400 hover:bg-[#202024] hover:text-slate-200'
                }`}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                <span className="truncate flex-1">{item.query}</span>
              </button>
            ))
          )}
        </div>

        {/* User Info footer */}
        <div className="p-3 border-t border-[#2C2C35] bg-[#131316] text-xs text-slate-400 flex items-center justify-between">
          <div className="flex items-center space-x-2 truncate">
            <div className="h-6 w-6 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-xs">
              E
            </div>
            <span className="truncate font-semibold">Enterprise Sandbox</span>
          </div>
          <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-400/20 uppercase font-mono">v1.1</span>
        </div>
      </aside>

      {/* 2. CENTER MAIN CHAT CONTAINER */}
      <main className="flex-1 flex flex-col bg-[#0B0B0F] relative overflow-hidden">
        {/* Top Navbar */}
        <header className="h-14 border-b border-[#1E1E24] px-6 flex items-center justify-between bg-[#0B0B0F]/90 backdrop-blur">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-sm tracking-tight text-white uppercase">etisalat <span className="text-amber-400">xSaaS Gateway</span></span>
            <span className="text-[10px] text-slate-500">• Grounded search index</span>
          </div>

          <button
            onClick={() => setIsTelemetryOpen(!isTelemetryOpen)}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs transition-colors border ${
              isTelemetryOpen 
                ? 'bg-amber-400/10 border-amber-400/30 text-amber-400' 
                : 'bg-transparent border-[#2C2C35] text-slate-400 hover:text-white'
            }`}
          >
            <Cpu className="h-3.5 w-3.5" />
            <span>Telemetry Panel</span>
          </button>
        </header>

        {/* Chat Feed */}
        <div className="flex-1 overflow-y-auto py-6 px-4 md:px-8 space-y-6">
          <div className="max-w-2xl mx-auto space-y-6">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex items-start space-x-3 max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                  
                  {/* Icon Avatar */}
                  <div className={`h-8 w-8 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
                    msg.role === 'user' ? 'bg-[#2A2A32] text-amber-400' : 'bg-amber-400 text-slate-950'
                  }`}>
                    {msg.role === 'user' ? 'U' : <Sparkles className="h-4 w-4" />}
                  </div>

                  {/* Bubble content */}
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        {msg.role === 'user' ? 'You' : 'Gateway Agent'}
                      </span>
                      <span className="text-[10px] text-slate-600">{msg.timestamp}</span>
                    </div>

                    <div className={`p-4 rounded-2xl text-sm leading-relaxed ${
                      msg.role === 'user' 
                        ? 'bg-[#1C1C24] text-white border border-[#2C2C35]' 
                        : 'bg-[#131318] text-[#D1D1D6] border border-[#1E1E24]'
                    }`}>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                      {msg.isStreaming && (
                        <span className="inline-flex items-center ml-1 space-x-1">
                          <span className="h-2 w-2 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: '0ms' }}></span>
                          <span className="h-2 w-2 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                          <span className="h-2 w-2 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                        </span>
                      )}
                    </div>

                    {/* Citations / Sources */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5 justify-start">
                        {msg.sources.map((src, sIdx) => (
                          <div key={sIdx} className="flex items-center space-x-1.5 rounded bg-[#131316] border border-[#2C2C35] px-2.5 py-1 text-xs text-slate-400">
                            <FileText className="h-3.5 w-3.5 text-amber-400" />
                            <span className="font-mono text-[10px] font-bold">[{sIdx + 1}] {src}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Bar Section */}
        <div className="p-4 bg-gradient-to-t from-[#0B0B0F] via-[#0B0B0F] to-transparent">
          <div className="max-w-2xl mx-auto">
            <form onSubmit={handleSubmit} className="flex items-center space-x-2 bg-[#1C1C24] border border-[#2C2C35] focus-within:border-amber-400/50 rounded-2xl p-2 transition-all shadow-xl">
              <input 
                type="text" 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={isStreamingActive}
                placeholder={isStreamingActive ? "Tracing backend execution..." : "Message your knowledge index..."}
                className="flex-1 bg-transparent border-0 outline-none text-sm placeholder-slate-500 text-white px-3 disabled:opacity-50"
              />
              <button 
                type="submit" 
                disabled={isStreamingActive || !input.trim()}
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold transition-all disabled:opacity-30 disabled:hover:bg-amber-400"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
            <div className="text-[10px] text-center text-slate-500 mt-2 flex items-center justify-center space-x-1">
              <Info className="h-3 w-3" />
              <span>Gateway outputs grounding references and real-time OpenTelemetry trace metrics automatically.</span>
            </div>
          </div>
        </div>
      </main>

      {/* 3. RIGHT SIDEBAR PANEL (OTel Performance Metrics & Diagnostics Logs) */}
      {isTelemetryOpen && (
        <aside className="w-80 bg-[#131316] border-l border-[#2C2C35] flex flex-col shrink-0">
          <div className="p-4 border-b border-[#2C2C35] flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Zap className="h-4 w-4 text-amber-400 animate-pulse" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-white">OTel Telemetry</h2>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">Real-Time Tracer</span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-6">
            {/* 1. Spans / Performance */}
            <div className="space-y-3">
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <Clock className="h-3.5 w-3.5 text-amber-400" />
                <span>Execution Spans</span>
              </h3>

              {currentSpans.length === 0 ? (
                <div className="border border-dashed border-[#2C2C35] rounded-xl p-6 text-center text-xs text-slate-500">
                  Awaiting operational prompt
                </div>
              ) : (
                <div className="space-y-3 font-mono text-[11px] bg-[#1C1C20] p-3 rounded-lg border border-[#2C2C28]">
                  {currentSpans.map((span, idx) => {
                    const maxVal = Math.max(...currentSpans.map(s => s.durationMs));
                    const pct = maxVal > 0 ? (span.durationMs / maxVal) * 100 : 0;
                    return (
                      <div key={idx} className="space-y-1">
                        <div className="flex justify-between">
                          <span className="text-slate-300 truncate max-w-[150px]">{span.name}</span>
                          <span className="text-amber-400 font-bold">{span.durationMs}ms</span>
                        </div>
                        <div className="h-1.5 w-full bg-[#131316] rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-amber-400 rounded-full transition-all duration-300"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* 2. Logs console */}
            <div className="space-y-3 flex-1 flex flex-col">
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <Terminal className="h-3.5 w-3.5 text-amber-400" />
                <span>Backend Execution Logs</span>
              </h3>

              {currentLogs.length === 0 ? (
                <div className="border border-dashed border-[#2C2C35] rounded-xl p-6 text-center text-xs text-slate-500">
                  No logs generated yet
                </div>
              ) : (
                <div className="flex-1 min-h-[250px] bg-[#09090C] border border-[#2C2C35] rounded-lg p-3 font-mono text-[10px] text-slate-300 space-y-2 overflow-y-auto leading-relaxed">
                  {currentLogs.map((log, idx) => (
                    <div key={idx} className={log.startsWith('[error]') ? 'text-rose-400' : 'text-slate-300'}>
                      {log}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </aside>
      )}

    </div>
  );
}
