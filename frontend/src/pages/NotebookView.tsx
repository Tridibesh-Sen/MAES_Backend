import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  LogOut, BookOpenCheck, BarChart2, ScrollText, Settings,
  ArrowLeft, Plus, FileText, Globe, Video, StickyNote,
  RefreshCw, PlayCircle, StopCircle, CheckCircle2, Activity
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, Cell, CartesianGrid
} from 'recharts';
import { supabase } from '../lib/supabaseClient';
import api from '../lib/apiClient';
import SourcesPanel from '../components/SourcesPanel';
import ChatPanel from '../components/ChatPanel';
import StudioPanel from '../components/StudioPanel';

/* ─── Interfaces ─── */
interface Source {
  id: string;
  notebookId: string;
  sourceType: 'pdf' | 'url' | 'youtube' | 'paste';
  title: string;
  isActive: boolean;
  createdAt: string;
}

interface Message {
  role: 'student' | 'tutor' | 'dvs' | 'peer';
  text: string;
  bloom_tag?: string;
  dvs_payload?: string;
  streaming?: boolean;
}

interface Flashcard { id: string; deckId: string; front: string; back: string; status: 'unseen' | 'review' | 'mastered'; sortOrder: number; }
interface FlashcardDeck { id: string; notebookId: string; title: string; createdAt: string; cards: Flashcard[]; }
interface QuizQuestion { id: string; question: string; options: string[]; correct_index: number; explanation: string; bloom_level: string; }
interface Quiz { id: string; questions: QuizQuestion[]; }

type ActiveView = 'workspace' | 'analytics' | 'logs' | 'settings';
type UploadType = 'pdf' | 'url' | 'youtube' | 'paste';

const BLOOM_CHART_COLORS: Record<string, string> = {
  remember: '#A0D4B0', understand: '#6BAF82', apply: '#4A7C59',
  analyze: '#3A6347', evaluate: '#2F5E3A', create: '#1A2E22',
};

export default function NotebookView() {
  const { notebookId } = useParams<{ notebookId: string }>();
  const navigate = useNavigate();
  const chatBottomRef = useRef<HTMLDivElement>(null);

  /* ── View ── */
  const [activeView, setActiveView] = useState<ActiveView>('workspace');
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  /* ── Core ── */
  const [notebook, setNotebook] = useState<any>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [inputText, setInputText] = useState('');
  const [currentRegister, setCurrentRegister] = useState('socratic');

  // Auth state - resolved together to avoid race conditions
  const [authReady, setAuthReady] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [authToken, setAuthToken] = useState<string | undefined>();

  /* ── Studio ── */
  const [studioTab, setStudioTab] = useState<'notes' | 'flashcards' | 'quiz' | 'study_guide'>('notes');
  const [notes, setNotes] = useState('');

  /* ── Upload Modal ── */
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadType, setUploadType] = useState<UploadType>('pdf');
  const [urlInput, setUrlInput] = useState('');
  const [pasteTitle, setPasteTitle] = useState('');
  const [pasteContent, setPasteContent] = useState('');
  const [fileInput, setFileInput] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  /* ── Flashcards ── */
  const [flashcardDecks, setFlashcardDecks] = useState<FlashcardDeck[]>([]);
  const [activeDeck, setActiveDeck] = useState<FlashcardDeck | null>(null);
  const [currentCardIdx, setCurrentCardIdx] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [isGeneratingCards, setIsGeneratingCards] = useState(false);
  const [flashcardTopic, setFlashcardTopic] = useState('');

  /* ── Quiz ── */
  const [currentQuiz, setCurrentQuiz] = useState<Quiz | null>(null);
  const [quizDifficulty, setQuizDifficulty] = useState<'easy' | 'medium' | 'hard'>('medium');
  const [quizSize, setQuizSize] = useState(5);
  const [isGeneratingQuiz, setIsGeneratingQuiz] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, number>>({});
  const [submittedQuiz, setSubmittedQuiz] = useState(false);

  /* ── Study Guide ── */
  const [studyGuide, setStudyGuide] = useState<string | null>(null);
  const [isGeneratingGuide, setIsGeneratingGuide] = useState(false);

  /* ── Analytics ── */
  const [telemetrySessions, setTelemetrySessions] = useState<any[]>([]);
  const [telemetryLogs, setTelemetryLogs] = useState<any[]>([]);
  const [telemetryLoading, setTelemetryLoading] = useState(false);

  /* ── Preferences ── */
  const [preferredRegister, setPreferredRegister] = useState('socratic');
  const [sessionTtl, setSessionTtl] = useState(30);

  /* ── Connectivity & System Status ── */
  const [isOnline, setIsOnline] = useState(true);
  const [systemStatus, setSystemStatus] = useState<any>(null);

  /* ═══ Effects ═══ */

  // Dynamic system health polling
  useEffect(() => {
    const fetchSystemStatus = async () => {
      try {
        const { data } = await api.get('/system-status');
        if (data) {
          setSystemStatus(data);
          setIsOnline(data.status === 'online');
        }
      } catch {
        setIsOnline(false);
      }
    };
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 8000);
    return () => clearInterval(interval);
  }, []);

  // Step 1: Resolve auth FIRST, then mark ready
  useEffect(() => {
    const resolveAuth = async () => {
      try {
        const { data: { user: sbUser } } = await supabase.auth.getUser();
        const { data: { session } } = await supabase.auth.getSession();

        if (sbUser && session) {
          setUser(sbUser);
          setAuthToken(session.access_token);
        } else {
          const demo = localStorage.getItem('maes_demo_session');
          if (demo) {
            setUser(JSON.parse(demo).user);
            setAuthToken('DEMO_USER_TOKEN');
          }
        }
      } catch {
        const demo = localStorage.getItem('maes_demo_session');
        if (demo) {
          setUser(JSON.parse(demo).user);
          setAuthToken('DEMO_USER_TOKEN');
        }
      } finally {
        setAuthReady(true);
      }
    };
    resolveAuth();
    fetchNotebookDetails();
    fetchSources();
    loadNotes();
    loadLocalFlashcards();
    loadLocalQuiz();
    loadLocalStudyGuide();
  }, [notebookId]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatLoading]);

  useEffect(() => {
    let interval: any;
    if (activeView === 'analytics' || activeView === 'logs') {
      fetchTelemetryData();
      if (activeView === 'logs') interval = setInterval(fetchTelemetryData, 3000);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [activeView, sessionId]);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        await api.get('/');
        setIsOnline(true);
      } catch {
        setIsOnline(false);
      }
    };
    checkConnection();
    const interval = setInterval(checkConnection, 3000);
    return () => clearInterval(interval);
  }, []);

  // Step 2: Only start session AFTER auth is resolved (authReady + user + notebook)
  useEffect(() => {
    if (authReady && user && notebook && !sessionId) {
      handleStartSession();
    }
  }, [authReady, user, notebook]);

  const fetchNotebookDetails = async () => {
    try {
      const { data } = await api.get(`/notebooks/${notebookId}`);
      if (data?.notebook) {
        setNotebook(data.notebook);
        return;
      }
    } catch {
      // Look in local cache
      const cached = localStorage.getItem('maes_local_notebooks');
      if (cached) {
        try {
          const list = JSON.parse(cached);
          const found = list.find((n: any) => n.id === notebookId);
          if (found) {
            setNotebook(found);
            return;
          }
        } catch {}
      }
    }
    setNotebook({ id: notebookId, title: 'Learning Session', domain: 'General Science' });
  };

  const fetchSources = async () => {
    try {
      const { data } = await api.get(`/sources/${notebookId}`);
      if (data?.sources && data.sources.length > 0) {
        setSources(data.sources);
        localStorage.setItem(`maes_sources_${notebookId}`, JSON.stringify(data.sources));
        return;
      }
    } catch { /* fail silently */ }
    const cached = localStorage.getItem(`maes_sources_${notebookId}`);
    if (cached) {
      try { setSources(JSON.parse(cached)); } catch {}
    }
  };

  const loadNotes = () => {
    const saved = localStorage.getItem(`maes_notes_${notebookId}`);
    setNotes(saved || '');
  };
  const handleNotesChange = (val: string) => {
    setNotes(val);
    localStorage.setItem(`maes_notes_${notebookId}`, val);
  };

  /* ═══ Source Handlers ═══ */
  const handleToggleSource = async (id: string, currentActive: boolean) => {
    try {
      await api.patch(`/sources/${id}/toggle`, { is_active: !currentActive });
    } catch { /* local fallback */ }
    setSources(s => {
      const next = s.map(src => src.id === id ? { ...src, isActive: !currentActive } : src);
      localStorage.setItem(`maes_sources_${notebookId}`, JSON.stringify(next));
      return next;
    });
  };

  const handleDeleteSource = async (id: string) => {
    try { await api.delete(`/sources/${id}`); } catch { /* local fallback */ }
    setSources(s => {
      const next = s.filter(src => src.id !== id);
      localStorage.setItem(`maes_sources_${notebookId}`, JSON.stringify(next));
      return next;
    });
  };

  const handleIngestSource = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsUploading(true);
    try {
      let responseData: any = null;
      if (uploadType === 'paste') {
        const { data } = await api.post('/sources/paste', { notebook_id: notebookId, title: pasteTitle || 'Pasted Text', content: pasteContent });
        responseData = data?.source;
      } else if (uploadType === 'url') {
        const { data } = await api.post('/sources/import-url', { notebook_id: notebookId, url: urlInput });
        responseData = data?.source;
      } else if (uploadType === 'youtube') {
        const { data } = await api.post('/sources/import-youtube', { notebook_id: notebookId, url: urlInput });
        responseData = data?.source;
      } else if (uploadType === 'pdf') {
        if (!fileInput) return;
        const formData = new FormData();
        formData.append('notebook_id', notebookId || '');
        formData.append('file', fileInput);
        const { data } = await api.post('/sources/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        responseData = data?.source;
      }
      if (responseData) {
        setSources(prev => {
          const next = [...prev, responseData];
          localStorage.setItem(`maes_sources_${notebookId}`, JSON.stringify(next));
          return next;
        });
      }
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
      setIsUploadModalOpen(false);
      setUrlInput(''); setPasteTitle(''); setPasteContent(''); setFileInput(null);
    }
  };

  /* ═══ Session Handlers ═══ */
  const handleStartSession = async () => {
    const studentId = user?.id || '123e4567-e89b-12d3-a456-426614174000';
    const domain = notebook?.domain || 'General Science';
    try {
      const { data } = await api.post('/session/start', { student_id: studentId, domain, notebook_id: notebookId });
      setSessionId(data.session_id);
      setMessages([{
        role: 'tutor',
        text: `Welcome! Your AI tutor is ready to help you explore "${domain}". Share what you understand about the topic, and I'll guide you with questions to deepen your thinking.`,
        bloom_tag: 'remember'
      }]);
    } catch {
      const sid = `sess-${Math.random().toString(36).substr(2, 9)}`;
      setSessionId(sid);
      setMessages([{
        role: 'tutor',
        text: `Welcome! Your AI tutor is ready to help you explore "${domain}". Share what you understand about the topic, and I'll guide you with questions to deepen your thinking.`,
        bloom_tag: 'remember'
      }]);
    }
  };

  const handleEndSession = async () => {
    if (!sessionId) return;
    try { await api.post('/session/end', { session_id: sessionId }); } catch { /* ok */ }
    setSessionId(null);
    setMessages([]);
  };

  /* ═══ Flashcard Handlers ═══ */
  const loadLocalFlashcards = () => {
    const cached = localStorage.getItem(`maes_flashcards_${notebookId}`);
    if (cached) {
      const decks = JSON.parse(cached);
      setFlashcardDecks(decks);
      if (decks.length > 0) { setActiveDeck(decks[0]); }
    }
  };

  const handleGenerateFlashcards = async () => {
    setIsGeneratingCards(true);
    try {
      const { data } = await api.post(
        '/studio/flashcards', 
        { notebook_id: notebookId, topic: flashcardTopic || 'Key Concepts' },
        { headers: authToken ? { Authorization: `Bearer ${authToken}` } : {} }
      );
      if (data?.deck) {
        const updated = [data.deck, ...flashcardDecks];
        setFlashcardDecks(updated); setActiveDeck(data.deck);
        setCurrentCardIdx(0); setIsFlipped(false);
        localStorage.setItem(`maes_flashcards_${notebookId}`, JSON.stringify(updated));
      }
    } catch { /* fail silently */ }
    setIsGeneratingCards(false);
  };

  const handleCardMastery = (status: 'review' | 'mastered') => {
    if (!activeDeck) return;
    const cards = [...activeDeck.cards];
    cards[currentCardIdx].status = status;
    const updatedDeck = { ...activeDeck, cards };
    const updatedDecks = flashcardDecks.map(d => d.id === activeDeck.id ? updatedDeck : d);
    setFlashcardDecks(updatedDecks); setActiveDeck(updatedDeck);
    localStorage.setItem(`maes_flashcards_${notebookId}`, JSON.stringify(updatedDecks));
    if (currentCardIdx < cards.length - 1) {
      setTimeout(() => { setIsFlipped(false); setCurrentCardIdx(p => p + 1); }, 300);
    }
  };

  /* ═══ Quiz Handlers ═══ */
  const loadLocalQuiz = () => {
    const cached = localStorage.getItem(`maes_quiz_${notebookId}`);
    if (cached) setCurrentQuiz(JSON.parse(cached));
  };

  const handleGenerateQuiz = async () => {
    setIsGeneratingQuiz(true); setQuizAnswers({}); setSubmittedQuiz(false);
    try {
      const { data } = await api.post(
        '/studio/quiz', 
        { notebook_id: notebookId, num_questions: quizSize, difficulty: quizDifficulty },
        { headers: authToken ? { Authorization: `Bearer ${authToken}` } : {} }
      );
      if (data?.quiz) { 
        setCurrentQuiz(data.quiz); 
        localStorage.setItem(`maes_quiz_${notebookId}`, JSON.stringify(data.quiz)); 
      }
    } catch { /* fail silently */ }
    setIsGeneratingQuiz(false);
  };

  const calculateQuizScore = () => {
    if (!currentQuiz) return 0;
    return currentQuiz.questions.reduce((acc, q, idx) => acc + (quizAnswers[idx] === q.correct_index ? 1 : 0), 0);
  };

  /* ═══ Study Guide ═══ */
  const loadLocalStudyGuide = () => {
    const cached = localStorage.getItem(`maes_studyguide_${notebookId}`);
    if (cached) setStudyGuide(cached);
  };
  const handleGenerateGuide = async () => {
    setIsGeneratingGuide(true);
    try {
      const { data } = await api.post(
        '/studio/study-guide', 
        { notebook_id: notebookId },
        { headers: authToken ? { Authorization: `Bearer ${authToken}` } : {} }
      );
      if (data?.study_guide?.markdown) {
        setStudyGuide(data.study_guide.markdown);
        localStorage.setItem(`maes_studyguide_${notebookId}`, data.study_guide.markdown);
      }
    } catch { /* fail silently */ }
    setIsGeneratingGuide(false);
  };

  /* ═══ Analytics ═══ */
  const fetchTelemetryData = async () => {
    setTelemetryLoading(true);
    try {
      const { data } = await api.get('/audit/dashboard/summary');
      if (data?.sessions) setTelemetrySessions(data.sessions);
    } catch { /* fail silently */ }
    if (sessionId) {
      try {
        const { data } = await api.get(`/audit/logs/${sessionId}`);
        if (data?.logs) setTelemetryLogs(data.logs);
      } catch { /* fail silently */ }
    }
    setTelemetryLoading(false);
  };

  /* ═══ Notebook Deletion ═══ */
  const handleDeleteCurrentNotebook = async () => {
    if (!notebookId) return;
    try {
      await api.delete(`/notebooks/${notebookId}`, {
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : {}
      });
    } catch { /* fail silently */ }
    
    // Clear local storage entries
    localStorage.removeItem(`maes_sources_${notebookId}`);
    localStorage.removeItem(`maes_notes_${notebookId}`);
    localStorage.removeItem(`maes_flashcards_${notebookId}`);
    localStorage.removeItem(`maes_quiz_${notebookId}`);
    localStorage.removeItem(`maes_studyguide_${notebookId}`);
    
    const localNbs = localStorage.getItem('maes_local_notebooks');
    if (localNbs) {
      try {
        const parsed = JSON.parse(localNbs).filter((n: any) => n.id !== notebookId);
        localStorage.setItem('maes_local_notebooks', JSON.stringify(parsed));
      } catch {}
    }
    
    navigate('/');
  };

  /* ═══ Logout ═══ */
  const handleLogout = async () => {
    await handleEndSession();
    localStorage.removeItem('maes_demo_session');
    await supabase.auth.signOut();
    window.dispatchEvent(new Event('maes_auth_change'));
    window.location.href = '/';
  };

  /* ─── Analytics chart data ─── */
  const bloomChartData = React.useMemo(() => {
    const counts: Record<string, number> = {};
    messages.filter(m => m.role === 'tutor' && m.bloom_tag).forEach(m => {
      counts[m.bloom_tag!] = (counts[m.bloom_tag!] || 0) + 1;
    });
    return Object.entries(counts).map(([name, count]) => ({ name, count }));
  }, [messages]);

  const navItems: { key: ActiveView; label: string; icon: React.ReactNode }[] = [
    { key: 'workspace', label: 'Workspace', icon: <BookOpenCheck size={15} /> },
    { key: 'analytics', label: 'Analytics', icon: <BarChart2 size={15} /> },
    { key: 'logs',      label: 'Session Logs', icon: <ScrollText size={15} /> },
    { key: 'settings',  label: 'Preferences', icon: <Settings size={15} /> },
  ];

  return (
    <div style={{ height: '100vh', width: '100%', display: 'flex', flexDirection: 'column', background: 'var(--off-white)', overflow: 'hidden', fontFamily: 'Inter, sans-serif' }}>

      {/* ═══════════════ NAVBAR ═══════════════ */}
      <header className="navbar" style={{ padding: '0 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
          <Link
            to="/"
            style={{
              width: 36, height: 36, background: 'var(--stone-100)',
              border: '1.5px solid var(--stone-300)', borderRadius: 'var(--radius)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--ink)', transition: 'all 0.15s',
            }}
            title="Back to notebooks"
          >
            <ArrowLeft size={16} />
          </Link>
          <div>
            <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--ink)', lineHeight: 1.25 }}>
              {notebook?.title || 'Loading...'}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--stone-500)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>{notebook?.domain || '...'}</span>
              {sessionId && (
                <span style={{ color: 'var(--green)', display: 'flex', alignItems: 'center', gap: '0.3rem', fontWeight: 600 }}>
                  <span style={{ width: 7, height: 7, background: 'var(--green)', borderRadius: '50%', animation: 'pulse 1.5s infinite' }} />
                  Session active
                </span>
              )}
            </div>
          </div>
        </div>

        <nav className="navbar-nav">
          {navItems.map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => setActiveView(key)}
              className={`nav-tab ${activeView === key ? 'active' : ''}`}
              style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}
            >
              {icon}
              <span className="hidden md:inline">{label}</span>
            </button>
          ))}
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          {/* Session Start/End */}
          {activeView === 'workspace' && (
            sessionId ? (
              <button onClick={handleEndSession} className="btn btn-secondary btn-sm" style={{ color: 'var(--error)', borderColor: 'rgba(192,57,43,0.3)' }}>
                <StopCircle size={14} /> End Session
              </button>
            ) : (
              <button onClick={handleStartSession} className="btn btn-primary btn-sm" disabled={!authReady}>
                <PlayCircle size={14} /> Start Session
              </button>
            )
          )}
          <button onClick={handleLogout} className="btn btn-ghost btn-sm" title="Sign out">
            <LogOut size={15} />
          </button>
        </div>
      </header>

      {/* ═══════════════ MAIN CONTENT ═══════════════ */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>

        {/* 1. WORKSPACE */}
        {activeView === 'workspace' && (
          <div style={{ height: '100%', display: 'flex', overflow: 'hidden' }}>
            <SourcesPanel
              sources={sources}
              handleDeleteSource={handleDeleteSource}
              handleToggleSource={handleToggleSource}
              setIsUploadModalOpen={setIsUploadModalOpen}
            />
            <ChatPanel
              messages={messages}
              setMessages={setMessages}
              currentRegister={currentRegister}
              setCurrentRegister={setCurrentRegister}
              chatLoading={chatLoading}
              setChatLoading={setChatLoading}
              sessionId={sessionId}
              inputText={inputText}
              setInputText={setInputText}
              chatBottomRef={chatBottomRef}
              authToken={authToken}
              isOnline={isOnline}
            />
            <StudioPanel
              studioTab={studioTab}
              setStudioTab={setStudioTab}
              notes={notes}
              handleNotesChange={handleNotesChange}
              flashcardTopic={flashcardTopic}
              setFlashcardTopic={setFlashcardTopic}
              handleGenerateFlashcards={handleGenerateFlashcards}
              isGeneratingCards={isGeneratingCards}
              sources={sources}
              activeDeck={activeDeck}
              currentCardIdx={currentCardIdx}
              setCurrentCardIdx={setCurrentCardIdx}
              isFlipped={isFlipped}
              setIsFlipped={setIsFlipped}
              handleCardMastery={handleCardMastery}
              currentQuiz={currentQuiz}
              setCurrentQuiz={setCurrentQuiz}
              quizDifficulty={quizDifficulty}
              setQuizDifficulty={setQuizDifficulty}
              quizSize={quizSize}
              setQuizSize={setQuizSize}
              handleGenerateQuiz={handleGenerateQuiz}
              isGeneratingQuiz={isGeneratingQuiz}
              quizAnswers={quizAnswers}
              setQuizAnswers={setQuizAnswers}
              submittedQuiz={submittedQuiz}
              setSubmittedQuiz={setSubmittedQuiz}
              calculateQuizScore={calculateQuizScore}
              studyGuide={studyGuide}
              isGeneratingGuide={isGeneratingGuide}
              handleGenerateGuide={handleGenerateGuide}
            />
          </div>
        )}

        {/* 2. ANALYTICS */}
        {activeView === 'analytics' && (
          <div className="telemetry-view">
            <div className="telemetry-header">
              <div>
                <h2 className="telemetry-title">Session Analytics</h2>
                <p className="telemetry-subtitle">Bloom taxonomy progression, cognitive load, and AI tutor decision history.</p>
              </div>
              <button onClick={fetchTelemetryData} disabled={telemetryLoading} className="btn btn-secondary btn-sm">
                <RefreshCw size={14} className={telemetryLoading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>

            {/* Stat Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
              {[
                { label: 'Total Messages', value: messages.length, sub: 'in this session', icon: <Activity size={20} style={{ color: 'var(--green)' }} /> },
                { label: 'AI Responses', value: messages.filter(m => m.role === 'tutor').length, sub: 'tutor turns', icon: <CheckCircle2 size={20} style={{ color: 'var(--green)' }} /> },
                { label: 'Knowledge Sources', value: sources.filter(s => s.isActive).length, sub: 'active documents', icon: <BookOpenCheck size={20} style={{ color: 'var(--green)' }} /> },
                { label: 'Sessions Logged', value: telemetrySessions.length, sub: 'in database', icon: <ScrollText size={20} style={{ color: 'var(--green)' }} /> },
              ].map((stat) => (
                <div key={stat.label} className="stat-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span className="stat-card-label">{stat.label}</span>
                    {stat.icon}
                  </div>
                  <div className="stat-card-value">{stat.value}</div>
                  <div className="stat-card-sub">{stat.sub}</div>
                </div>
              ))}
            </div>

            {/* Bloom Chart */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
              <div className="chart-card">
                <h3 className="chart-card-title">Bloom's Taxonomy Distribution</h3>
                {bloomChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={bloomChartData} barCategoryGap="30%">
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--stone-200)" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--stone-500)', style: { textTransform: 'capitalize' } }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: 'var(--stone-400)' }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ background: 'var(--white)', border: '1px solid var(--stone-200)', borderRadius: 8, fontSize: 12 }} />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {bloomChartData.map((entry) => (
                          <Cell key={entry.name} fill={BLOOM_CHART_COLORS[entry.name] || '#4A7C59'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--stone-400)', fontSize: '0.875rem' }}>
                    Start a learning session to see your Bloom progression.
                  </div>
                )}
              </div>

              <div className="chart-card">
                <h3 className="chart-card-title">Session History</h3>
                {telemetrySessions.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={telemetrySessions.slice(-10)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--stone-200)" />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--stone-400)' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--stone-400)' }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ background: 'var(--white)', border: '1px solid var(--stone-200)', borderRadius: 8, fontSize: 12 }} />
                      <Line type="monotone" dataKey="bloom_score" stroke="var(--green)" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--stone-400)', fontSize: '0.875rem', textAlign: 'center', padding: '1rem' }}>
                    Analytics data will appear here after you've completed sessions.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 3. SESSION LOGS */}
        {activeView === 'logs' && (
          <div className="logs-view">
            <div className="logs-header">
              <div className="logs-title">
                <ScrollText size={16} />
                AI Tutor Decision Log
                <span className="logs-live-dot" />
              </div>
              <span style={{ fontSize: '0.75rem', color: 'rgba(160,212,176,0.5)', fontFamily: 'JetBrains Mono, monospace' }}>
                {sessionId ? `Session: ${sessionId.slice(0, 12)}...` : 'No active session'}
              </span>
            </div>
            <div className="logs-body">
              {telemetryLogs.length === 0 ? (
                <div style={{ color: 'rgba(160,212,176,0.4)', fontSize: '0.8rem', padding: '2rem', textAlign: 'center' }}>
                  No log entries yet. Start a session and ask a question to see AI decision logs here.
                </div>
              ) : (
                telemetryLogs.map((log: any, idx) => {
                  let badgeClass = 'approved';
                  let badgeText = 'APPROVED';
                  
                  if (log.event === 'agent_a' || log.event === 'agent_a_draft') { badgeClass = 'agent_a'; badgeText = 'AGENT A'; }
                  else if (log.event === 'agent_b' || log.event === 'agent_b_done') { badgeClass = 'agent_b'; badgeText = 'AGENT B'; }
                  else if (log.event === 'agent_p' || log.event === 'agent_p_challenge') { badgeClass = 'agent_p'; badgeText = 'AGENT P'; }
                  else if (log.event === 'ccli') { badgeClass = 'ccli'; badgeText = 'CCLI'; }
                  else if (log.event === 'orchestrator') { badgeClass = 'orchestrator'; badgeText = 'ORCHESTRATOR'; }
                  else if (log.event === 'gcd') { badgeClass = 'gcd'; badgeText = 'GCD'; }
                  else if (log.event === 'dvs') { badgeClass = 'dvs'; badgeText = 'DVS'; }
                  else if (log.event === 'fallback') { badgeClass = 'fallback'; badgeText = 'FALLBACK LLM'; }
                  else if (log.event === 'dashboard') { badgeClass = 'dashboard'; badgeText = 'DASHBOARD'; }
                  else if (log.status === 'rejected') { badgeClass = 'rejected'; badgeText = 'REVISED'; }

                  return (
                    <div key={idx} className="log-entry">
                      <span className="log-time">{log.time || (log.created_at ? new Date(log.created_at).toLocaleTimeString() : '')}</span>
                      <span className={`log-event-badge ${badgeClass}`}>
                        {badgeText}
                      </span>
                      <span className="log-text">{log.text || log.decision_reason || 'Audit entry logged.'}</span>
                    </div>
                  );
                })
              )}
              <div className="log-cursor">█</div>
            </div>
          </div>
        )}

        {/* 4. PREFERENCES */}
        {activeView === 'settings' && (
          <div className="pref-view" style={{ overflowY: 'auto', padding: '2rem 1rem' }}>
            <div style={{ maxWidth: 680, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--ink)', marginBottom: '0.25rem', letterSpacing: '-0.02em' }}>Preferences & System Architecture</h2>
                <p style={{ fontSize: '0.875rem', color: 'var(--stone-500)' }}>Configure pedagogical settings and inspect the live multi-agent and control subsystems.</p>
              </div>

              {/* Teaching Style */}
              <div className="pref-section">
                <h3 className="pref-section-title">Active Pedagogical Register</h3>
                <p className="pref-section-desc">Select the primary instructional scaffolding strategy used by Agent A (Teacher).</p>
                <label className="pref-label" htmlFor="pref-register">Scaffold Mode</label>
                <select
                  id="pref-register"
                  value={preferredRegister}
                  onChange={(e) => setPreferredRegister(e.target.value)}
                  className="input select"
                >
                  <option value="socratic">Socratic Questioning — Probe student thinking with open questions</option>
                  <option value="analogy">Analogy-First — Anchor target concepts in intuitive physical metaphors</option>
                  <option value="cognitive_conflict">Challenge Mode — Agent P peer epistemic misconception conflict</option>
                  <option value="worked_example">Worked Example — Step-by-step structural modeling</option>
                  <option value="error_correction">Error Correction — Targeted remediation on detected errors</option>
                </select>
              </div>

              {/* Active 5-Agent Suite */}
              <div className="pref-section">
                <h3 className="pref-section-title">Multi-Agent AI Network (Active)</h3>
                <p className="pref-section-desc">Coordinated multi-model agent network actively auditing and generating dialogue.</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem', marginTop: '0.75rem' }}>
                  {systemStatus?.agents ? (
                    Object.entries(systemStatus.agents).map(([key, ag]: [string, any]) => {
                      const status = ag.status || 'offline';
                      const isOnline = status === 'online';
                      const isFallback = status === 'fallback';

                      const badgeColor = isOnline ? 'var(--green-800)' : isFallback ? '#DC2626' : 'var(--stone-600)';
                      const badgeBg = isOnline ? 'var(--green-100)' : isFallback ? 'rgba(220, 38, 38, 0.12)' : 'var(--stone-200)';
                      const badgeBorder = isOnline ? 'rgba(74, 124, 89, 0.25)' : isFallback ? 'rgba(220, 38, 38, 0.35)' : 'rgba(0, 0, 0, 0.1)';
                      const dotColor = isOnline ? '#10B981' : isFallback ? '#DC2626' : '#9CA3AF';
                      const statusLabel = isOnline ? 'Active' : isFallback ? 'Fallback' : 'Offline';

                      return (
                        <div
                          key={key}
                          style={{
                            padding: '0.875rem 1rem',
                            background: isFallback ? 'rgba(254, 242, 242, 0.6)' : 'var(--stone-50)',
                            borderRadius: 'var(--radius)',
                            border: `1px solid ${isFallback ? 'rgba(239, 68, 68, 0.3)' : 'var(--stone-200)'}`,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '0.5rem'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--ink)' }}>{ag.name}</span>
                              <span
                                style={{
                                  fontSize: '0.75rem',
                                  color: isFallback ? '#B91C1C' : 'var(--stone-600)',
                                  background: isFallback ? 'rgba(254, 226, 226, 0.8)' : 'var(--stone-200)',
                                  border: isFallback ? '1px solid rgba(239, 68, 68, 0.2)' : 'none',
                                  padding: '1px 6px',
                                  borderRadius: '4px',
                                  fontFamily: 'JetBrains Mono, monospace'
                                }}
                              >
                                {ag.model}
                              </span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              {ag.calls > 0 && (
                                <span
                                  style={{
                                    fontSize: '0.7rem',
                                    color: isFallback ? '#B91C1C' : 'var(--green-800)',
                                    background: isFallback ? 'rgba(254, 226, 226, 0.8)' : 'var(--green-100)',
                                    padding: '2px 7px',
                                    borderRadius: '10px',
                                    fontWeight: 600
                                  }}
                                >
                                  {ag.calls} turn{ag.calls !== 1 ? 's' : ''} {isFallback ? 'fallback' : 'active'}
                                </span>
                              )}
                              <span
                                className="badge"
                                style={{
                                  fontSize: '0.7rem',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  color: badgeColor,
                                  background: badgeBg,
                                  border: `1px solid ${badgeBorder}`,
                                  fontWeight: 600
                                }}
                              >
                                <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor }} />
                                {statusLabel}
                              </span>
                            </div>
                          </div>

                          <p style={{ fontSize: '0.8125rem', color: 'var(--stone-600)', margin: 0, lineHeight: 1.4 }}>
                            <strong>Use Case:</strong> {ag.usecase || ag.role}
                          </p>

                          {ag.trigger && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--stone-500)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                              <span style={{ fontWeight: 600, color: 'var(--stone-600)' }}>Trigger:</span> {ag.trigger}
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div style={{ fontSize: '0.875rem', color: 'var(--stone-400)', padding: '1rem 0' }}>Loading agent subsystem statuses...</div>
                  )}
                </div>
              </div>

              {/* Closed-Loop Control Engines */}
              <div className="pref-section">
                <h3 className="pref-section-title">Closed-Loop Pedagogical Engines</h3>
                <p className="pref-section-desc">Real-time control algorithms regulating struggle and cognitive load.</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem', marginTop: '0.5rem' }}>
                  {[
                    { name: 'Discrete PID Scaffolding Controller', desc: 'Regulates continuous scaffolding u[k] targeting optimal struggle (PSI = 0.40)', tag: 'Active' },
                    { name: 'CCLI Typing Telemetry Engine', desc: 'Passive chronometric keystroke & latency cognitive load calculation', tag: 'Active' },
                    { name: 'Multi-Dimensional Struggle PSI Engine', desc: 'Combines latency, backspaces, and concept semantic distance', tag: 'Active' },
                    { name: 'Epistemic Concept Dependency Graph', desc: 'Directed Acyclic Graph (DAG) for prerequisite concept traversal', tag: 'Active' },
                    { name: 'Multi-Format Universal Ingestion', desc: 'Parses PDF, Word (.docx), PowerPoint (.pptx), Markdown, JSON, and Code', tag: 'Active' },
                  ].map((eng) => (
                    <div key={eng.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.625rem 0.875rem', background: 'var(--stone-50)', borderRadius: 'var(--radius)', border: '1px solid var(--stone-200)' }}>
                      <div>
                        <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--ink)' }}>{eng.name}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--stone-500)' }}>{eng.desc}</div>
                      </div>
                      <span className="badge badge-green" style={{ fontSize: '0.7rem' }}>{eng.tag}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Active Infrastructure */}
              <div className="pref-section">
                <h3 className="pref-section-title">Live Cloud & Storage Services</h3>
                <p className="pref-section-desc">Production infrastructure services connected to this notebook session.</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
                  {systemStatus?.infrastructure ? (
                    Object.entries(systemStatus.infrastructure).map(([key, inf]: [string, any]) => {
                      const isInfConnected = inf.status === 'connected';
                      return (
                        <div key={key} style={{ padding: '0.75rem 1rem', background: 'var(--stone-50)', borderRadius: 'var(--radius)', border: '1px solid var(--stone-200)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ink)' }}>{inf.name}</span>
                            <span
                              className={`badge ${isInfConnected ? 'badge-green' : 'badge-stone'}`}
                              style={{
                                fontSize: '0.7rem',
                                color: isInfConnected ? 'var(--green-800)' : '#DC2626',
                                background: isInfConnected ? 'var(--green-100)' : 'rgba(220,38,38,0.1)'
                              }}
                            >
                              {isInfConnected ? 'Connected' : 'Offline'}
                            </span>
                          </div>
                          {inf.usecase && (
                            <p style={{ fontSize: '0.75rem', color: 'var(--stone-500)', margin: 0, lineHeight: 1.4 }}>
                              {inf.usecase}
                            </p>
                          )}
                        </div>
                      );
                    })
                  ) : null}
                </div>
              </div>

              {/* Session Timeout */}
              <div className="pref-section">
                <h3 className="pref-section-title">Session Memory & TTL</h3>
                <p className="pref-section-desc">How long the AI retains your conversation context before cache expiration.</p>
                <label className="pref-label">Timeout: {sessionTtl} minutes</label>
                <input
                  type="range" min={5} max={120} value={sessionTtl}
                  onChange={(e) => setSessionTtl(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--green)', marginBottom: '0.5rem' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--stone-400)' }}>
                  <span>5 min</span><span>120 min</span>
                </div>
              </div>

              {/* Danger Zone: Delete Notebook */}
              <div className="pref-section" style={{ borderColor: 'rgba(220, 38, 38, 0.3)', background: 'rgba(254, 242, 242, 0.5)' }}>
                <h3 className="pref-section-title" style={{ color: '#DC2626' }}>Danger Zone</h3>
                <p className="pref-section-desc">Permanently delete this notebook and all associated sources, notes, and session logs.</p>
                <button
                  onClick={() => setIsDeleteModalOpen(true)}
                  className="btn btn-sm"
                  style={{ background: '#DC2626', color: '#fff', fontWeight: 600, marginTop: '0.5rem' }}
                >
                  Delete This Notebook
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ═══════════════ ADD SOURCE MODAL ═══════════════ */}
      {isUploadModalOpen && (
        <div className="modal-overlay" onClick={() => setIsUploadModalOpen(false)}>
          <div className="modal-panel" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Add Knowledge Source</h2>

            {/* Type Tabs */}
            <div className="upload-type-tabs">
              {([
                { key: 'pdf', label: 'PDF / File', icon: FileText },
                { key: 'url', label: 'Web Article', icon: Globe },
                { key: 'youtube', label: 'YouTube', icon: Video },
                { key: 'paste', label: 'Paste Text', icon: StickyNote },
              ] as const).map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setUploadType(key)}
                  className={`upload-type-tab ${uploadType === key ? 'active' : ''}`}
                >
                  <Icon size={13} /> {label}
                </button>
              ))}
            </div>

            <form onSubmit={handleIngestSource} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {uploadType === 'pdf' && (
                <div>
                  <label className="pref-label">Choose file (PDF or TXT)</label>
                  <input
                    type="file" accept=".pdf,.txt"
                    onChange={(e) => setFileInput(e.target.files?.[0] ?? null)}
                    className="input" style={{ cursor: 'pointer', padding: '0.5rem' }}
                    required
                  />
                  <p style={{ fontSize: '0.75rem', color: 'var(--stone-400)', marginTop: '0.375rem' }}>
                    Text is extracted server-side and embedded for AI context.
                  </p>
                </div>
              )}
              {(uploadType === 'url' || uploadType === 'youtube') && (
                <div>
                  <label className="pref-label">{uploadType === 'youtube' ? 'YouTube video URL' : 'Article URL'}</label>
                  <input
                    type="url" value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    className="input"
                    placeholder={uploadType === 'youtube' ? 'https://youtube.com/watch?v=...' : 'https://example.com/article'}
                    required
                  />
                  <p style={{ fontSize: '0.75rem', color: 'var(--stone-400)', marginTop: '0.375rem' }}>
                    {uploadType === 'youtube' ? 'Transcript is fetched and embedded automatically.' : 'Page content is scraped and embedded for AI context.'}
                  </p>
                </div>
              )}
              {uploadType === 'paste' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
                  <div>
                    <label className="pref-label">Source title</label>
                    <input
                      type="text" value={pasteTitle}
                      onChange={(e) => setPasteTitle(e.target.value)}
                      className="input" placeholder="e.g. Lecture notes — Chapter 3"
                      required
                    />
                  </div>
                  <div>
                    <label className="pref-label">Content</label>
                    <textarea
                      value={pasteContent}
                      onChange={(e) => setPasteContent(e.target.value)}
                      className="input" rows={5} style={{ resize: 'vertical' }}
                      placeholder="Paste your text, notes, or transcript here..."
                      required
                    />
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.25rem' }}>
                <button type="button" onClick={() => setIsUploadModalOpen(false)} className="btn btn-secondary" style={{ flex: 1 }}>
                  Cancel
                </button>
                <button type="submit" disabled={isUploading} className="btn btn-primary" style={{ flex: 1 }}>
                  {isUploading ? (
                    <><RefreshCw size={14} className="animate-spin" /> Uploading...</>
                  ) : (
                    <><Plus size={14} /> Add Source</>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ═══════════════ DELETE NOTEBOOK MODAL ═══════════════ */}
      {isDeleteModalOpen && (
        <div className="modal-overlay" onClick={() => setIsDeleteModalOpen(false)}>
          <div className="modal-panel" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--ink)', marginBottom: '0.5rem' }}>Delete Notebook?</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--stone-500)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
              Are you sure you want to delete this notebook? All uploaded sources, flashcards, quizzes, notes, and session logs will be permanently deleted.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button onClick={() => setIsDeleteModalOpen(false)} className="btn btn-secondary btn-sm">Cancel</button>
              <button
                onClick={handleDeleteCurrentNotebook}
                className="btn btn-sm"
                style={{ background: '#DC2626', color: '#fff', fontWeight: 600 }}
              >
                Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════ STATUS BAR ═══════════════ */}
      <footer style={{
        height: 32, background: 'var(--green-900)',
        color: 'rgba(160,212,176,0.7)',
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.25rem',
        flexShrink: 0,
        fontSize: '0.7rem',
        fontFamily: 'JetBrains Mono, monospace',
        fontWeight: 500,
      }}>
        <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
          <span style={{ color: 'var(--green-400)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ width: 6, height: 6, background: 'var(--green-400)', borderRadius: '50%' }} />
            System Online
          </span>
          {sessionId && <span>Session: {sessionId.slice(0, 8)}...</span>}
          <span>{sources.filter(s => s.isActive).length} sources active</span>
        </div>
        <span>MAES · Adaptive AI Tutoring · v2.8</span>
      </footer>
    </div>
  );
}
