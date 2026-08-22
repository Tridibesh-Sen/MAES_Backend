import { useState } from 'react';
import { BookOpenCheck } from 'lucide-react';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleStartLearning = () => {
    setLoading(true);
    setError('');
    try {
      const mockSession = {
        access_token: 'DEMO_USER_TOKEN',
        user: {
          id: '123e4567-e89b-12d3-a456-426614174000',
          email: 'guest@maes-learning.org',
          role: 'student'
        }
      };
      localStorage.setItem('maes_demo_session', JSON.stringify(mockSession));
      window.dispatchEvent(new Event('maes_auth_change'));
    } catch (e: any) {
      setError(e.message || 'An error occurred.');
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        {/* Logo */}
        <div className="login-logo">
          <BookOpenCheck size={28} />
        </div>

        {/* Title */}
        <h1 className="login-title">MAES Learning</h1>
        <p className="login-subtitle">Adaptive AI tutoring powered by Socratic dialogue</p>

        {/* Login Action */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          <button
            onClick={handleStartLearning}
            className="btn btn-primary btn-full"
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              gap: '0.75rem',
              backgroundColor: 'var(--accent)',
              color: 'var(--canvas)',
              border: 'none',
              fontWeight: 600,
              boxShadow: '0 4px 10px rgba(0,0,0,0.15)'
            }}
          >
            {loading ? 'Initializing...' : 'Start Learning'}
          </button>
        </div>

        {/* Feedback Message */}
        {error && (
          <div style={{
            marginTop: '1rem',
            padding: '0.875rem 1rem',
            borderRadius: 'var(--radius)',
            background: 'var(--error-light)',
            border: '1px solid rgba(192,57,43,0.25)',
            color: 'var(--error)',
            fontSize: '0.875rem',
            lineHeight: 1.5,
          }}>
            {error}
          </div>
        )}

      </div>
    </div>
  );
}
