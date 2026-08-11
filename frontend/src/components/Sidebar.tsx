import React, { useEffect, useState } from 'react';
import { useAuthStore } from '../store/authStore';

export function Sidebar({ onSelectSession, currentSessionId, onNewAssessment }: any) {
  const [sessions, setSessions] = useState<any[]>([]);
  const { token } = useAuthStore();
  const API_URL = 'http://localhost:8000';

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
    <div style={{ width: '280px', background: 'var(--color-bg-panel)', borderRight: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', height: '100vh', padding: '24px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '32px', paddingLeft: '8px' }}>
        <div style={{ width: '32px', height: '32px', borderRadius: '10px', background: 'var(--color-emerald-glow)', border: '1px solid var(--color-emerald-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-emerald)' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        </div>
        <div>
          <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--color-text-primary)', letterSpacing: '-0.02em' }}>EnviroWealth</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '24px' }}>
        <button style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 12px', background: 'var(--color-emerald-deep)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-emerald-dim)', color: 'var(--color-emerald)', cursor: 'pointer', textAlign: 'left', fontWeight: 600 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          Chat
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '12px', paddingLeft: '8px', letterSpacing: '0.04em' }}>History</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {sessions.map(s => (
            <button key={s.session_id} onClick={() => onSelectSession(s.session_id)} style={{ padding: '8px 12px', background: s.session_id === currentSessionId ? 'var(--color-bg-deep)' : 'transparent', border: 'none', borderRadius: 'var(--radius-md)', color: s.session_id === currentSessionId ? 'var(--color-text-primary)' : 'var(--color-text-secondary)', cursor: 'pointer', textAlign: 'left', fontSize: '13px', transition: 'all 0.2s' }}>
              {s.preview}
            </button>
          ))}
          {sessions.length === 0 && <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', paddingLeft: '8px' }}>No previous sessions</div>}
        </div>
      </div>

      <button onClick={onNewAssessment} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '12px', background: 'var(--color-emerald)', color: '#000', border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 600, cursor: 'pointer', marginTop: 'auto', marginBottom: '16px' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        New Assessment
      </button>

      <div style={{ padding: '16px', background: 'var(--color-emerald-glow)', border: '1px solid var(--color-emerald-dim)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
         <div style={{ color: "var(--color-emerald)", fontSize: "16px", marginTop: "2px" }}>🛡️</div>
         <div>
            <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-emerald)", marginBottom: "4px" }}>Your data is secure</div>
            <div style={{ fontSize: "11px", color: "var(--color-emerald)", lineHeight: 1.4 }}>Information is used only for eligibility assessment.</div>
         </div>
      </div>
    </div>
  );
}
