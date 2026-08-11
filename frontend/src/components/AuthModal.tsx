import React, { useState } from 'react';
import { useAuthStore } from '../store/authStore';

export function AuthModal() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuthStore();

  const API_URL = 'http://localhost:8000';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const res = await fetch(`${API_URL}/api/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData.toString(),
        });
        
        if (!res.ok) {
           const err = await res.json();
           throw new Error(err.detail || 'Login failed');
        }
        const data = await res.json();
        setAuth(data.access_token, { id: '', email: data.email, full_name: data.full_name });
      } else {
        const res = await fetch(`${API_URL}/api/v1/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, full_name: fullName }),
        });
        
        if (!res.ok) {
           const err = await res.json();
           throw new Error(err.detail || 'Signup failed');
        }
        const data = await res.json();
        setAuth(data.access_token, { id: '', email: data.email, full_name: data.full_name });
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 9000, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(4px)" }}>
      <div style={{ background: "var(--color-bg-panel)", borderRadius: "var(--radius-xl)", width: "100%", maxWidth: "400px", padding: "32px", border: "1px solid var(--color-border)", boxShadow: "var(--shadow-panel)" }}>
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <h2 style={{ fontSize: "20px", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: "8px" }}>Welcome to EnviroWealth</h2>
          <p style={{ fontSize: "13px", color: "var(--color-text-secondary)" }}>{isLogin ? 'Log in to continue' : 'Sign up to get started'}</p>
        </div>
        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Full Name</label>
              <input type="text" required value={fullName} onChange={e => setFullName(e.target.value)} style={{ width: "100%", padding: "10px", background: "var(--color-bg-input)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)", outline: "none" }} />
            </div>
          )}
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Email</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)} style={{ width: "100%", padding: "10px", background: "var(--color-bg-input)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)", outline: "none" }} />
          </div>
          <div style={{ marginBottom: "24px" }}>
             <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Password</label>
             <input type="password" required value={password} onChange={e => setPassword(e.target.value)} style={{ width: "100%", padding: "10px", background: "var(--color-bg-input)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)", outline: "none" }} />
          </div>
          
          {error && <div style={{ color: 'var(--color-amber)', fontSize: '12px', marginBottom: '16px', textAlign: 'center' }}>{error}</div>}

          <button type="submit" disabled={loading} style={{ width: "100%", padding: "12px", background: "var(--color-emerald)", color: "#000", border: "none", borderRadius: "var(--radius-sm)", fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1, marginBottom: '16px' }}>
            {loading ? "Processing..." : (isLogin ? "Log In" : "Sign Up")}
          </button>
          
          <div style={{ textAlign: 'center', fontSize: '12px', color: 'var(--color-text-muted)' }}>
             {isLogin ? "Don't have an account? " : "Already have an account? "}
             <span style={{ color: 'var(--color-emerald)', cursor: 'pointer' }} onClick={() => {setIsLogin(!isLogin); setError('');}}>
               {isLogin ? "Sign Up" : "Log In"}
             </span>
          </div>
        </form>
      </div>
    </div>
  );
}
