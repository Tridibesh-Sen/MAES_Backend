import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BookOpenCheck, Plus, LogOut, BookOpen,
  Layers, Calendar, ChevronRight, User, RefreshCw, Trash2
} from 'lucide-react';
import { supabase } from '../lib/supabaseClient';
import api from '../lib/apiClient';

interface Notebook {
  id: string;
  title: string;
  domain: string;
  createdAt: string;
  updatedAt: string;
  sourceCount?: number;
}

const DOMAIN_OPTIONS = [
  'Computer Science',
  'Mathematics',
  'Physics',
  'Chemistry',
  'Biology',
  'Engineering',
  'Economics',
  'General Science',
];

export default function NotebookList() {
  const navigate = useNavigate();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDomain, setNewDomain] = useState('Computer Science');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  // Delete modal state
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    const getProfile = async () => {
      try {
        const { data: { user: sbUser } } = await supabase.auth.getUser();
        if (sbUser) {
          setUser(sbUser);
        } else {
          const demo = localStorage.getItem('maes_demo_session');
          if (demo) setUser(JSON.parse(demo).user);
        }
      } catch {
        const demo = localStorage.getItem('maes_demo_session');
        if (demo) setUser(JSON.parse(demo).user);
      }
    };
    getProfile();
    fetchNotebooks();
  }, []);

  const fetchNotebooks = async () => {
    setLoading(true);
    try {
      let token = 'DEMO_USER_TOKEN';
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        token = session.access_token;
      }
      
      const res = await api.get('/notebooks', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.data?.notebooks && Array.isArray(res.data.notebooks) && res.data.notebooks.length > 0) {
        setNotebooks(res.data.notebooks);
        localStorage.setItem('maes_local_notebooks', JSON.stringify(res.data.notebooks));
      } else {
        const local = localStorage.getItem('maes_local_notebooks');
        if (local) {
          setNotebooks(JSON.parse(local));
        } else {
          setNotebooks([]);
        }
      }
    } catch {
      const local = localStorage.getItem('maes_local_notebooks');
      if (local) {
        setNotebooks(JSON.parse(local));
      } else {
        setNotebooks([]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNotebook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || creating) return;

    setCreating(true);
    setCreateError('');

    try {
      let token = 'DEMO_USER_TOKEN';
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        token = session.access_token;
      }

      const res = await api.post('/notebooks', {
        title: newTitle.trim(),
        domain: newDomain,
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const nb = res.data.notebook;
      const updated = [nb, ...notebooks.filter(n => n.id !== nb.id)];
      setNotebooks(updated);
      localStorage.setItem('maes_local_notebooks', JSON.stringify(updated));
      setIsModalOpen(false);
      setNewTitle('');
      navigate(`/notebook/${nb.id}`);
    } catch {
      const fallbackNb: Notebook = {
        id: (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : 'nb-' + Math.random().toString(36).substring(2, 9),
        title: newTitle.trim(),
        domain: newDomain,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        sourceCount: 0
      };
      const updated = [fallbackNb, ...notebooks.filter(n => n.id !== fallbackNb.id)];
      setNotebooks(updated);
      localStorage.setItem('maes_local_notebooks', JSON.stringify(updated));
      setIsModalOpen(false);
      setNewTitle('');
      navigate(`/notebook/${fallbackNb.id}`);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteNotebook = async (e: React.MouseEvent, nbId: string) => {
    e.stopPropagation();
    try {
      let token = 'DEMO_USER_TOKEN';
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        token = session.access_token;
      }

      await api.delete(`/notebooks/${nbId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
    } catch {
      // ignore network errors on delete
    }

    const updated = notebooks.filter(n => n.id !== nbId);
    setNotebooks(updated);
    localStorage.setItem('maes_local_notebooks', JSON.stringify(updated));
    localStorage.removeItem(`maes_sources_${nbId}`);
    localStorage.removeItem(`maes_notes_${nbId}`);
    setDeletingId(null);
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    localStorage.removeItem('maes_demo_session');
    window.location.href = '/';
  };

  const firstName = user?.email?.split('@')[0] || 'Learner';

  return (
    <div className="notebooks-page">
      {/* Navbar */}
      <header className="navbar">
        <div className="navbar-brand">
          <div className="navbar-logo">
            <BookOpenCheck size={20} />
          </div>
          MAES Learning
        </div>

        <div className="navbar-actions">
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.375rem 0.875rem',
            background: 'var(--stone-100)',
            border: '1.5px solid var(--stone-200)',
            borderRadius: 'var(--radius)',
            fontSize: '0.8125rem',
            color: 'var(--stone-600)',
            fontWeight: 500,
          }}>
            <User size={14} />
            {user?.email || 'Guest Student'}
          </div>

          <button
            onClick={fetchNotebooks}
            disabled={loading}
            className="btn btn-secondary btn-sm"
            title="Refresh notebooks"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>

          <button onClick={handleLogout} className="btn btn-secondary btn-sm">
            <LogOut size={14} />
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="notebooks-main">
        {/* Welcome Banner */}
        <div className="welcome-banner">
          <div>
            <p className="welcome-greeting">Welcome back,</p>
            <h2 className="welcome-title">{firstName.charAt(0).toUpperCase() + firstName.slice(1)}</h2>
            <p className="welcome-subtitle">
              {notebooks.length > 0
                ? `You have ${notebooks.length} active notebook${notebooks.length > 1 ? 's' : ''}. Ready to learn?`
                : 'Create your first notebook to start an AI-guided learning session.'}
            </p>
          </div>
          <button
            onClick={() => { setCreateError(''); setIsModalOpen(true); }}
            className="btn"
            style={{
              background: '#fff',
              color: 'var(--green-800)',
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            <Plus size={18} />
            New Notebook
          </button>
        </div>

        {/* Section header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: '1.25rem'
        }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--ink)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BookOpen size={18} style={{ color: 'var(--green)' }} />
            My Notebooks
          </h3>
          <span style={{ fontSize: '0.8125rem', color: 'var(--stone-500)', fontWeight: 500 }}>
            {notebooks.length} {notebooks.length === 1 ? 'notebook' : 'notebooks'}
          </span>
        </div>

        {/* Notebooks grid */}
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '5rem', gap: '1rem', color: 'var(--stone-400)' }}>
            <div style={{ width: 32, height: 32, border: '3px solid var(--stone-200)', borderTopColor: 'var(--green)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Loading notebooks...</span>
          </div>
        ) : notebooks.length === 0 ? (
          <div style={{
            background: 'var(--white)',
            border: '2px dashed var(--stone-300)',
            borderRadius: 'var(--radius-xl)',
            padding: '4rem 2rem',
            textAlign: 'center',
          }}>
            <BookOpen size={48} style={{ color: 'var(--green-300)', margin: '0 auto 1rem' }} />
            <p style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--stone-600)', marginBottom: '0.5rem' }}>No notebooks yet</p>
            <p style={{ fontSize: '0.875rem', color: 'var(--stone-400)', marginBottom: '1.5rem' }}>
              Create your first notebook and start an AI-guided learning session.
            </p>
            <button onClick={() => { setCreateError(''); setIsModalOpen(true); }} className="btn btn-primary">
              <Plus size={16} /> Create Notebook
            </button>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.25rem' }}>
            {notebooks.map((nb) => (
              <div
                key={nb.id}
                onClick={() => navigate(`/notebook/${nb.id}`)}
                className="notebook-card"
                style={{ position: 'relative' }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
                  <span className="notebook-domain-badge">
                    <Layers size={10} />
                    {nb.domain}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--stone-400)', display: 'flex', alignItems: 'center', gap: '0.3rem', flexShrink: 0 }}>
                      <Calendar size={10} />
                      {new Date(nb.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); setDeletingId(nb.id); }}
                      title="Delete notebook"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--stone-400)',
                        cursor: 'pointer',
                        padding: '4px',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.15s'
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--error)')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--stone-400)')}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                <h4 className="notebook-title">{nb.title}</h4>

                <div className="notebook-meta">
                  <span className="notebook-meta-info">
                    <BookOpen size={12} />
                    {nb.sourceCount ?? 0} source{nb.sourceCount !== 1 ? 's' : ''}
                  </span>
                  <span className="notebook-open-link">
                    Open <ChevronRight size={14} />
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Delete Confirmation Modal */}
      {deletingId && (
        <div className="modal-overlay" onClick={() => setDeletingId(null)}>
          <div className="modal-panel" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--ink)', marginBottom: '0.5rem' }}>Delete Notebook?</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--stone-500)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
              Are you sure you want to delete this notebook? All uploaded sources, flashcards, notes, and session history will be permanently deleted.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button onClick={() => setDeletingId(null)} className="btn btn-secondary btn-sm">Cancel</button>
              <button
                onClick={(e) => handleDeleteNotebook(e, deletingId)}
                className="btn btn-sm"
                style={{ background: '#DC2626', color: '#fff', fontWeight: 600 }}
              >
                Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Notebook Modal */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Create New Notebook</h2>

            {createError && (
              <div style={{
                marginBottom: '1rem',
                padding: '0.625rem 0.875rem',
                borderRadius: 'var(--radius)',
                background: 'var(--error-light)',
                border: '1px solid rgba(192,57,43,0.25)',
                color: 'var(--error)',
                fontSize: '0.8125rem'
              }}>
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateNotebook} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                <label className="pref-label" htmlFor="nb-title">Notebook title</label>
                <input
                  id="nb-title"
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Machine Learning Fundamentals"
                  required
                  autoFocus
                  className="input"
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                <label className="pref-label" htmlFor="nb-domain">Domain / Field of study</label>
                <select
                  id="nb-domain"
                  value={newDomain}
                  onChange={(e) => setNewDomain(e.target.value)}
                  className="input select"
                >
                  {DOMAIN_OPTIONS.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newTitle.trim()}
                  className="btn btn-primary"
                >
                  {creating ? 'Creating...' : 'Create Notebook'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
