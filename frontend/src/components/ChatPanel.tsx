/**
 * ChatPanel — AI Tutor Conversation (Phase 3)
 * - CCLI keystroke tracking
 * - SSE streaming consumption (fixed event-based parsing)
 * - DVS Concept Diagram rendering
 * - Peer Perspective bubbles
 */
import React, { useState, useRef } from 'react';
import { MessageSquare, Send, Brain } from 'lucide-react';
import { useCCLI } from '../hooks/useCCLI';
import DVSViewer from './DVSViewer';

interface Message {
  role: 'student' | 'tutor' | 'dvs' | 'peer';
  text: string;
  bloom_tag?: string;
  dvs_payload?: string;
  streaming?: boolean;
}

interface ChatPanelProps {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  currentRegister: string;
  setCurrentRegister: (reg: string) => void;
  chatLoading: boolean;
  setChatLoading: (v: boolean) => void;
  sessionId: string | null;
  inputText: string;
  setInputText: (val: string) => void;
  chatBottomRef: React.RefObject<HTMLDivElement | null>;
  onCLSUpdate?: (cls: number) => void;
  authToken?: string;
  isOnline?: boolean;
}

const REGISTER_LABELS: Record<string, string> = {
  socratic:          'Socratic Mode',
  analogy:           'Analogy Mode',
  cognitive_conflict: 'Challenge Mode',
};

const BLOOM_COLORS: Record<string, string> = {
  remember:  '#A0D4B0',
  understand:'#6BAF82',
  apply:     '#4A7C59',
  analyze:   '#3A6347',
  evaluate:  '#2F5E3A',
  create:    '#234B30',
};

export default function ChatPanel({
  messages,
  setMessages,
  currentRegister,
  setCurrentRegister,
  chatLoading,
  setChatLoading,
  sessionId,
  inputText,
  setInputText,
  chatBottomRef,
  onCLSUpdate,
  authToken,
  isOnline = true,
}: ChatPanelProps) {
  const { cls, resetCLS, onKeyDown } = useCCLI();
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    onKeyDown(e);
    if (onCLSUpdate) onCLSUpdate(cls);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionId || !inputText.trim() || chatLoading) return;

    const userMessage = inputText.trim();
    const capturedCLS = cls;
    setInputText('');
    resetCLS();

    setMessages(prev => [...prev, { role: 'student', text: userMessage }]);
    setChatLoading(true);
    setStatusMsg('Connecting to AI tutor...');

    // Add streaming placeholder
    setMessages(prev => [...prev, { role: 'tutor', text: '', streaming: true }]);

    try {
      abortRef.current = new AbortController();
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

      const response = await fetch(`${baseUrl}/turn/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({
          session_id: sessionId,
          student_message: userMessage,
          chronometric_load_score: capturedCLS,
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let streamedText = '';
      let dvsPending: string | null = null;
      let currentEvent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            // Track which event type the next data line belongs to
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const rawData = line.slice(6).trim();
            if (!rawData) continue;
            try {
              const data = JSON.parse(rawData);

              if (currentEvent === 'status' || 'msg' in data) {
                setStatusMsg(data.msg);
              } else if (currentEvent === 'token' || 'token' in data) {
                streamedText += data.token;
                setMessages(prev => {
                  const updated = [...prev];
                  const lastTutor = [...updated].reverse().findIndex(m => m.role === 'tutor');
                  if (lastTutor >= 0) {
                    const idx = updated.length - 1 - lastTutor;
                    updated[idx] = { ...updated[idx], text: streamedText, streaming: true };
                  }
                  return updated;
                });
                chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
              } else if (currentEvent === 'dvs' || 'svg' in data) {
                if (data.svg) {
                  dvsPending = data.svg;
                }
              } else if (currentEvent === 'done' || 'bloom_tag' in data) {
                const finalBloom = data.bloom_tag;
                const finalReg = data.register;
                const isPeer = data.peer_challenge;
                const activeDvs = dvsPending;
                dvsPending = null;

                setMessages(prev => {
                  const updated = [...prev];
                  const lastTutor = [...updated].reverse().findIndex(m => m.role === 'tutor');
                  if (lastTutor >= 0) {
                    const idx = updated.length - 1 - lastTutor;
                    updated[idx] = { 
                      ...updated[idx], 
                      text: streamedText || updated[idx].text, 
                      bloom_tag: finalBloom, 
                      streaming: false, 
                      role: isPeer ? 'peer' : 'tutor' 
                    };
                  }
                  if (activeDvs) {
                    updated.push({ role: 'dvs', text: '', dvs_payload: activeDvs });
                  }
                  return updated;
                });

                if (finalReg) setCurrentRegister(finalReg);
                setStatusMsg(null);
              } else if (currentEvent === 'error' || 'error' in data) {
                const errMsg = data.error || 'An error occurred during response generation.';
                setMessages(prev => {
                  const updated = [...prev];
                  const lastTutor = [...updated].reverse().findIndex(m => m.role === 'tutor');
                  if (lastTutor >= 0) {
                    const idx = updated.length - 1 - lastTutor;
                    updated[idx] = { ...updated[idx], text: `[Error: ${errMsg}]`, streaming: false };
                  }
                  return updated;
                });
                setStatusMsg(null);
              }
            } catch { /* skip malformed lines */ }
            // Reset event tracker after consuming data
            currentEvent = '';
          } else if (line === '') {
            // blank line resets the event tracking per SSE spec
            currentEvent = '';
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('[ChatPanel] SSE error:', err.message);
        setMessages(prev => {
          const updated = [...prev];
          const lastTutor = [...updated].reverse().findIndex(m => m.role === 'tutor');
          if (lastTutor >= 0) {
            const idx = updated.length - 1 - lastTutor;
            const errMsg = err.message?.includes('401')
              ? "Authentication failed. Please refresh the page and try again."
              : err.message?.includes('404')
              ? "Session expired. Please click 'End Session' then 'Start Session' to begin again."
              : "I'm having trouble connecting. Please try again.";
            updated[idx] = { ...updated[idx], text: errMsg, streaming: false };
          }
          return updated;
        });
      }
    } finally {
      setChatLoading(false);
      setStatusMsg(null);
      abortRef.current = null;
    }
  };

  return (
    <section className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <span className="chat-header-title">
          <MessageSquare size={16} className="chat-header-icon" />
          AI Tutor
        </span>
        <div className="chat-header-right">
          <span className="register-badge">{REGISTER_LABELS[currentRegister] || currentRegister}</span>
          {cls > 0.5 && (
            <span className="cls-badge" title={`Cognitive load detected: ${(cls * 100).toFixed(0)}%`}>
              🧠 High load
            </span>
          )}
          <span
            className={`badge ${isOnline ? 'badge-green' : 'badge-stone'}`}
            style={{
              fontSize: '0.65rem',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontWeight: 600,
              color: isOnline ? 'var(--green-800)' : '#DC2626',
              background: isOnline ? 'var(--green-100)' : 'rgba(220,38,38,0.1)',
              border: `1px solid ${isOnline ? 'rgba(74,124,89,0.2)' : 'rgba(220,38,38,0.2)'}`
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: isOnline ? '#10B981' : '#DC2626',
                display: 'inline-block'
              }}
            />
            {isOnline ? 'Agents Online' : 'Agents Offline'}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <MessageSquare size={44} className="chat-empty-icon" />
            <p className="chat-empty-title">Start the conversation</p>
            <p className="chat-empty-subtitle">
              {sessionId
                ? 'Type your question or share your understanding of the topic below.'
                : 'Waiting for a session to be established...'}
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => {
            if (msg.role === 'dvs') {
              if (!msg.dvs_payload) return null;
              return (
                <div key={idx} className="chat-dvs-wrapper" style={{ margin: '0.75rem 0' }}>
                  <DVSViewer svgPayload={msg.dvs_payload} />
                </div>
              );
            }

            if (!msg.text && !msg.streaming) {
              return null;
            }

            const isPeer = msg.role === 'peer';
            const isStudent = msg.role === 'student';
            return (
              <div
                key={idx}
                className={`chat-message ${isStudent ? 'chat-message--student' : isPeer ? 'chat-message--peer' : 'chat-message--tutor'}`}
              >
                <div className="chat-message-meta">
                  <span className={`chat-role-label ${isStudent ? 'chat-role-label--student' : isPeer ? 'chat-role-label--peer' : 'chat-role-label--tutor'}`}>
                    {isStudent ? 'You' : isPeer ? (
                      <><Brain size={11} style={{ display: 'inline' }} /> Peer Perspective</>
                    ) : 'AI Tutor'}
                  </span>
                  {msg.bloom_tag && (
                    <span className="bloom-badge" style={{
                      background: BLOOM_COLORS[msg.bloom_tag] + '22',
                      color: BLOOM_COLORS[msg.bloom_tag] || 'var(--green-700)',
                      borderColor: BLOOM_COLORS[msg.bloom_tag] + '55',
                    }}>
                      {msg.bloom_tag}
                    </span>
                  )}
                  {msg.streaming && <span className="streaming-dot" />}
                </div>
                <div className={`chat-bubble ${isStudent ? 'chat-bubble--student' : isPeer ? 'chat-bubble--peer' : 'chat-bubble--tutor'}`}>
                  <p className="chat-bubble-text">{msg.text}</p>
                  {msg.dvs_payload && (
                    <div style={{ marginTop: '0.75rem' }}>
                      <DVSViewer svgPayload={msg.dvs_payload} />
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Thinking indicator */}
        {chatLoading && statusMsg && (
          <div className="chat-thinking">
            <div className="chat-thinking-dots">
              <div className="dot dot--1" />
              <div className="dot dot--2" />
              <div className="dot dot--3" />
            </div>
            <span className="chat-thinking-label">{statusMsg}</span>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSendMessage} className="chat-input-form">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!sessionId || chatLoading}
          className="chat-input"
          placeholder={sessionId ? 'Share your understanding or ask a question...' : 'Session not started yet...'}
        />
        <button
          type="submit"
          disabled={!sessionId || chatLoading || !inputText.trim()}
          className="chat-send-btn"
        >
          <Send size={15} />
          Send
        </button>
      </form>
    </section>
  );
}
