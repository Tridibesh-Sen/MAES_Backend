import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import NotebookView from './pages/NotebookView';
import NotebookList from './pages/NotebookList';

import LoginPage from './pages/LoginPage';
import { supabase } from './lib/supabaseClient';

function App() {
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const { data: { session: sbSession } } = await supabase.auth.getSession();
        if (sbSession) {
          setSession(sbSession);
        } else {
          const demo = localStorage.getItem('maes_demo_session');
          setSession(demo ? JSON.parse(demo) : null);
        }
      } catch (e) {
        const demo = localStorage.getItem('maes_demo_session');
        setSession(demo ? JSON.parse(demo) : null);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, sbSession) => {
      if (sbSession) {
        setSession(sbSession);
      } else {
        const demo = localStorage.getItem('maes_demo_session');
        setSession(demo ? JSON.parse(demo) : null);
      }
    });

    const handleCustomAuth = () => {
      const demo = localStorage.getItem('maes_demo_session');
      setSession(demo ? JSON.parse(demo) : null);
    };

    window.addEventListener('maes_auth_change', handleCustomAuth);
    window.addEventListener('storage', handleCustomAuth);

    return () => {
      subscription.unsubscribe();
      window.removeEventListener('maes_auth_change', handleCustomAuth);
      window.removeEventListener('storage', handleCustomAuth);
    };
  }, []);

  if (loading) {
    return <div className="min-h-screen bg-canvas text-ink flex items-center justify-center font-mono font-bold uppercase tracking-widest">Initializing...</div>;
  }

  if (!session) {
    return <LoginPage />;
  }

  return (
    <Router>
      <Routes>
        <Route 
          path="/" 
          element={<NotebookList />} 
          key="notebook-list-route"
        />
        <Route 
          path="/notebook/:notebookId" 
          element={<NotebookView />} 
          key="notebook-view-route"
        />
        {/* Redirect any stray /login or unknown routes to root */}
        <Route 
          path="/login" 
          element={<Navigate to="/" replace />} 
          key="login-route"
        />
        <Route 
          path="*" 
          element={<Navigate to="/" replace />} 
          key="catch-all-route"
        />
      </Routes>
    </Router>
  );
}

export default App;

