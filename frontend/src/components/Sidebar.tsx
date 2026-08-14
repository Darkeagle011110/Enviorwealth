import React, { useEffect, useState } from 'react';
import { useAuthStore } from '../store/authStore';

export function Sidebar({ onSelectSession, currentSessionId, onNewAssessment }: any) {
  const [sessions, setSessions] = useState<any[]>([]);
  const [isSecureCardCollapsed, setIsSecureCardCollapsed] = useState(false);
  const { token } = useAuthStore();
  const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsSecureCardCollapsed(true);
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (token) {
      fetch(`${API_URL}/api/v1/user/sessions`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) setSessions(data);
        })
        .catch(console.error);
    }
  }, [token, currentSessionId]);

  return (
    <div style={{ width: '280px', background: 'var(--color-bg-panel)', borderRight: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', height: '100vh', position: 'relative' }}>

      {/* Top Content Area */}
      <div style={{ padding: '24px 16px', display: 'flex', flexDirection: 'column', flex: 1, zIndex: 10 }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', paddingLeft: '8px' }}>
          <div style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-emerald-deep)' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z" /><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" stroke="currentColor" strokeWidth="2" fill="none" /></svg>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontWeight: 700, fontSize: '22px', color: 'var(--color-text-primary)', letterSpacing: '-0.02em', lineHeight: 1.1 }}>EnviroWealth</span>
            <span style={{ fontSize: '12px', color: 'var(--color-emerald)', fontWeight: 600 }}>Carbon Eligibility Assessor</span>
          </div>
        </div>

        <div style={{ borderBottom: '1px solid var(--color-border)', margin: '16px 0', marginLeft: '8px', marginRight: '8px' }} />

        {/* Navigation */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '24px' }}>
          <button onClick={onNewAssessment} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 16px', background: '#f3f4f6', borderRadius: 'var(--radius-md)', border: 'none', color: 'var(--color-emerald)', cursor: 'pointer', textAlign: 'left', fontWeight: 600, fontSize: '14px' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
            New Chat
          </button>
        </div>

        <div style={{ borderBottom: '1px solid var(--color-border)', margin: '0 8px 16px 8px' }} />

        {/* History */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--color-text-muted)', marginBottom: '12px', paddingLeft: '8px' }}>History</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {sessions.map(s => (
              <button key={s.session_id} onClick={() => onSelectSession(s.session_id)} style={{ padding: '8px 12px', background: s.session_id === currentSessionId ? 'var(--color-bg-card-hover)' : 'transparent', border: 'none', borderRadius: 'var(--radius-md)', color: s.session_id === currentSessionId ? 'var(--color-text-primary)' : 'var(--color-text-secondary)', cursor: 'pointer', textAlign: 'left', fontSize: '13px', transition: 'all 0.2s' }}>
                {s.preview}
              </button>
            ))}
            {sessions.length === 0 && <div style={{ fontSize: '13px', color: 'var(--color-text-muted)', paddingLeft: '8px' }}>No previous sessions</div>}
          </div>
        </div>
      </div>

      {/* Bottom Content Area with Background */}
      <div style={{
        padding: '24px 16px',
        marginTop: 'auto',
        position: 'relative',
        minHeight: '480px',
        display: 'flex',
        alignItems: 'flex-end'
      }}>
        {/* Background Image Container */}
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundImage: 'url(/sidebar-bg.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'top center',
          opacity: 0.9,
          zIndex: 1,
          borderTopLeftRadius: '24px'
        }} />

        {/* White Overlay Gradient to blend image */}
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, height: '40px',
          background: 'linear-gradient(to bottom, var(--color-bg-panel), transparent)',
          zIndex: 2
        }} />

        {/* Security Card */}
        <div 
          onClick={() => setIsSecureCardCollapsed(!isSecureCardCollapsed)}
          style={{
          padding: '16px',
          background: 'rgba(255, 255, 255, 0.95)',
          border: '1px solid rgba(229, 231, 235, 0.8)',
          borderRadius: 'var(--radius-lg)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 10,
          width: '100%',
          boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
          cursor: 'pointer',
          transition: 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
          maxHeight: isSecureCardCollapsed ? '52px' : '200px',
          overflow: 'hidden'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', height: '20px' }}>
            <div style={{ color: "var(--color-emerald)", display: 'flex' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
            </div>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--color-text-primary)" }}>Your data is secure</div>
          </div>
          
          <div style={{ 
            opacity: isSecureCardCollapsed ? 0 : 1,
            transition: 'opacity 0.4s ease',
            marginTop: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <div style={{ fontSize: "12px", color: "var(--color-text-secondary)", lineHeight: 1.4 }}>
              We use industry-standard security and your information is never shared.
            </div>
            <a href="#" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-emerald)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px' }}>
              Learn more <span style={{ fontSize: '14px' }}>→</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
