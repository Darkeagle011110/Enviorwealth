"use client";

import { useState, useRef, useEffect, useCallback } from "react";

import { Sidebar } from '../components/Sidebar';
import { AuthModal } from '../components/AuthModal';
import { useAuthStore } from '../store/authStore';


// ─── Types ────────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp?: Date;
}

interface FinancialRange {
  annual_credits_range: [number, number];
  revenue_usd_range: [number, number];
  first_issuance_years: [number, number];
}

interface VerdictData {
  category: string;
  confidence: number;
  confidence_reason?: string;
  is_eligible: boolean;
  knockout_gate?: string;
}

interface DocumentChecklistItem {
  doc: string;
  source: string;
}

interface Memo {
  generated_at: string;
  verdict: VerdictData;
  why: string;
  disclaimer: string;
  financials?: FinancialRange;
  risk_flags?: string[];
  next_steps?: string[];
  alternatives?: string[];
  developer_questions?: string[];
  unverified_fields?: string[];
  document_checklist?: DocumentChecklistItem[];
}

interface UIState {
  stage?: string;
  progress?: number;
  filled_fields?: number;
  total_fields?: number;
  current_field?: string;
  show_memo_button?: boolean;
  verdict_category?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const VERDICT_META: Record<string, { label: string; cls: string; icon: string; desc: string }> = {
  promising_proceed_feasibility: {
    label: "Promising — Proceed to Feasibility",
    cls: "verdict-promising",
    icon: "✦",
    desc: "Your land shows strong eligibility signals. We recommend engaging a verified project developer.",
  },
  possible_needs_aggregation: {
    label: "Possible — Aggregation Needed",
    cls: "verdict-aggregation",
    icon: "◈",
    desc: "Eligibility is possible but your parcel may need to be pooled with neighbouring land.",
  },
  ecological_caution: {
    label: "Ecological Caution",
    cls: "verdict-caution",
    icon: "⬡",
    desc: "Ecological sensitivities detected. Certain high-biodiversity features must be protected — not replaced.",
  },
  unlikely_economic: {
    label: "Unlikely — Economic Barrier",
    cls: "verdict-possible",
    icon: "◇",
    desc: "Technically eligible, but the project economics don't justify the costs at current scale or prices.",
  },
  not_eligible_structural: {
    label: "Not Eligible — Structural",
    cls: "verdict-ineligible",
    icon: "✗",
    desc: "A structural requirement of current Indian carbon methodologies is not met.",
  },
  insufficient_information: {
    label: "Insufficient Information",
    cls: "verdict-insufficient",
    icon: "?",
    desc: "More information is needed before a verdict can be determined.",
  },
};

const FIELD_LABELS: Record<string, string> = {
  area_ha: "Land Area",
  tenure_type: "Tenure Type",
  land_legal_class: "Legal Classification",
  existing_tree_cover_pct: "Tree Cover %",
  planting_status: "Planting Status",
  would_plant_anyway: "Additionality",
};

// ─── Inline SVG Icons ─────────────────────────────────────────────────────────
const LeafIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z" />
    <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
  </svg>
);

const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const MapIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" /><line x1="9" y1="3" x2="9" y2="18" /><line x1="15" y1="6" x2="15" y2="21" />
  </svg>
);

const ChevronIcon = ({ open }: { open: boolean }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s ease" }}>
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

// ─── Sub-components ───────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "4px", padding: "14px 18px", background: "var(--color-bg-card)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md)", maxWidth: "80px", animation: "fadeIn 0.3s ease" }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--color-emerald)", animation: `typingDot 1.2s ease ${i * 0.2}s infinite`, display: "block" }} />
      ))}
    </div>
  );
}

function ProgressBar({ progress, filledFields, totalFields, currentField }: { progress: number; filledFields: number; totalFields: number; currentField?: string }) {
  return (
    <div style={{ padding: "12px 16px", background: "var(--color-bg-card)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md)", marginBottom: "8px", animation: "fadeIn 0.3s ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-emerald)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Screening Progress
        </span>
        <span style={{ fontSize: "11px", color: "var(--color-text-secondary)" }}>
          {filledFields}/{totalFields} fields
        </span>
      </div>
      <div style={{ height: "4px", background: "var(--color-bg-deep)", borderRadius: "9999px", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${progress * 100}%`, background: "linear-gradient(90deg, var(--color-emerald-dim), var(--color-emerald))", borderRadius: "9999px", transition: "width 0.5s var(--ease-smooth)" }} />
      </div>
      {currentField && (
        <p style={{ marginTop: "6px", fontSize: "11px", color: "var(--color-text-muted)" }}>
          Asking about: <span style={{ color: "var(--color-text-secondary)" }}>{FIELD_LABELS[currentField] ?? currentField}</span>
        </p>
      )}
    </div>
  );
}

function VerdictCard({ memo }: { memo: Memo }) {
  const [openSection, setOpenSection] = useState<string | null>("why");
  const vm = VERDICT_META[memo.verdict.category] ?? VERDICT_META.insufficient_information;
  const conf = Math.round(memo.verdict.confidence);

  const toggle = (sec: string) => setOpenSection(prev => prev === sec ? null : sec);

  return (
    <div className={vm.cls} style={{ border: "1px solid var(--v-border)", borderRadius: "var(--radius-xl)", overflow: "hidden", animation: "scaleIn 0.4s var(--ease-spring)", background: "var(--color-bg-card)", boxShadow: "var(--shadow-panel)" }}>

      {/* Header */}
      <div style={{ padding: "24px", background: "linear-gradient(135deg, var(--v-bg) 0%, transparent 60%)", borderBottom: "1px solid var(--v-border)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: "16px" }}>
          <div style={{ width: "48px", height: "48px", borderRadius: "14px", background: "var(--v-bg)", border: "1px solid var(--v-border)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "22px", color: "var(--v-color)", flexShrink: 0 }}>
            {vm.icon}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--v-color)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "4px" }}>
              Eligibility Verdict
            </div>
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--color-text-primary)", lineHeight: 1.2, marginBottom: "8px" }}>
              {vm.label}
            </h2>
            <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
              {vm.desc}
            </p>
          </div>
        </div>

        {/* Confidence meter */}
        <div style={{ marginTop: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
            <span style={{ fontSize: "11px", color: "var(--color-text-muted)", fontWeight: 500 }}>Confidence Score</span>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--v-color)" }}>{conf}/100</span>
          </div>
          <div style={{ height: "6px", background: "var(--color-bg-deep)", borderRadius: "9999px", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${conf}%`, background: `linear-gradient(90deg, var(--v-color)88, var(--v-color))`, borderRadius: "9999px", transition: "width 1s var(--ease-smooth)" }} />
          </div>
          {memo.verdict.confidence_reason && (
            <p style={{ marginTop: "6px", fontSize: "11px", color: "var(--color-text-muted)", fontStyle: "italic" }}>
              {memo.verdict.confidence_reason}
            </p>
          )}
        </div>
      </div>

      {/* Financials */}
      {memo.financials && (
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--color-border)", background: "var(--color-emerald-deep)" }}>
          <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--color-emerald)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "14px" }}>
            Indicative Numbers
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
            {[
              { label: "Credits / year", val: `${memo.financials.annual_credits_range[0].toLocaleString()}–${memo.financials.annual_credits_range[1].toLocaleString()}`, unit: "tCO₂e" },
              { label: "Revenue / year", val: `$${memo.financials.revenue_usd_range[0].toLocaleString()}–$${memo.financials.revenue_usd_range[1].toLocaleString()}`, unit: "USD" },
              { label: "First issuance", val: `Yr ${memo.financials.first_issuance_years[0]}–${memo.financials.first_issuance_years[1]}`, unit: "from start" },
            ].map((item) => (
              <div key={item.label} style={{ background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md)", padding: "12px" }}>
                <div style={{ fontSize: "10px", color: "var(--color-text-muted)", marginBottom: "4px", fontWeight: 500 }}>{item.label}</div>
                <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--color-emerald)", lineHeight: 1.1 }}>{item.val}</div>
                <div style={{ fontSize: "10px", color: "var(--color-text-muted)", marginTop: "2px" }}>{item.unit}</div>
              </div>
            ))}
          </div>

          {/* Cash-flow curve */}
          <CashFlowCurve firstIssuance={memo.financials.first_issuance_years[0]} />
        </div>
      )}

      {/* Accordion sections */}
      <div style={{ padding: "8px" }}>
        {memo.why && (
          <Accordion id="why" label="Why this verdict?" open={openSection === "why"} onToggle={() => toggle("why")}>
            <p style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.7 }}>{memo.why}</p>
          </Accordion>
        )}

        {memo.risk_flags && memo.risk_flags.length > 0 && (
          <Accordion id="flags" label={`Risk Flags (${memo.risk_flags.length})`} open={openSection === "flags"} onToggle={() => toggle("flags")} accent="amber">
            <ul style={{ listStyle: "none" }}>
              {memo.risk_flags.map((flag, i) => (
                <li key={i} style={{ display: "flex", gap: "10px", padding: "8px 0", borderBottom: i < memo.risk_flags!.length - 1 ? "1px solid var(--color-border)" : "none", alignItems: "flex-start" }}>
                  <span style={{ color: "var(--color-amber)", fontSize: "16px", marginTop: "1px", flexShrink: 0 }}>⚠</span>
                  <span style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>{flag}</span>
                </li>
              ))}
            </ul>
          </Accordion>
        )}

        {memo.next_steps && memo.next_steps.length > 0 && (
          <Accordion id="steps" label="Next Steps" open={openSection === "steps"} onToggle={() => toggle("steps")} accent="blue">
            <ol style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "10px" }}>
              {memo.next_steps.map((step, i) => (
                <li key={i} style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <span style={{ width: "22px", height: "22px", borderRadius: "50%", background: "var(--color-blue-dim)", border: "1px solid var(--color-blue)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "11px", fontWeight: 700, color: "var(--color-blue)", flexShrink: 0 }}>{i + 1}</span>
                  <span style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.5, paddingTop: "3px" }}>{step}</span>
                </li>
              ))}
            </ol>
          </Accordion>
        )}

        {memo.document_checklist && memo.document_checklist.length > 0 && (
          <Accordion id="docs" label="Document Checklist" open={openSection === "docs"} onToggle={() => toggle("docs")} accent="violet">
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {memo.document_checklist.map((item, i) => (
                <div key={i} style={{ padding: "10px 12px", background: "var(--color-bg-panel)", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-border)" }}>
                  <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-text-primary)", marginBottom: "2px" }}>✓ {item.doc}</div>
                  <div style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>Source: {item.source}</div>
                </div>
              ))}
            </div>
          </Accordion>
        )}

        {memo.developer_questions && memo.developer_questions.length > 0 && (
          <Accordion id="devq" label="Questions to Ask a Developer" open={openSection === "devq"} onToggle={() => toggle("devq")}>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "8px" }}>
              {memo.developer_questions.map((q, i) => (
                <li key={i} style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.5, paddingLeft: "16px", borderLeft: "2px solid var(--color-border-strong)" }}>
                  {q}
                </li>
              ))}
            </ul>
          </Accordion>
        )}

        {memo.alternatives && memo.alternatives.length > 0 && (
          <Accordion id="alt" label="Alternatives to Explore" open={openSection === "alt"} onToggle={() => toggle("alt")}>
            <ul style={{ listStyle: "none" }}>
              {memo.alternatives.map((alt, i) => (
                <li key={i} style={{ fontSize: "13px", color: "var(--color-text-secondary)", lineHeight: 1.5, display: "flex", gap: "8px", padding: "6px 0" }}>
                  <span style={{ color: "var(--color-emerald-dim)" }}>→</span> {alt}
                </li>
              ))}
            </ul>
          </Accordion>
        )}

        {memo.unverified_fields && memo.unverified_fields.length > 0 && (
          <Accordion id="unver" label="What We Couldn't Check" open={openSection === "unver"} onToggle={() => toggle("unver")}>
            <ul style={{ listStyle: "none" }}>
              {memo.unverified_fields.map((f, i) => (
                <li key={i} style={{ fontSize: "13px", color: "var(--color-text-muted)", lineHeight: 1.5, display: "flex", gap: "8px", padding: "5px 0" }}>
                  <span style={{ color: "var(--color-text-disabled)" }}>○</span> {f}
                </li>
              ))}
            </ul>
          </Accordion>
        )}
      </div>

      {/* Disclaimer */}
      <div style={{ padding: "16px 24px", borderTop: "1px solid var(--color-border)", background: "rgba(0,0,0,0.2)" }}>
        <p style={{ fontSize: "11px", color: "var(--color-text-muted)", lineHeight: 1.6, fontStyle: "italic" }}>
          ⚖️ {memo.disclaimer}
        </p>
      </div>
    </div>
  );
}

function Accordion({ id, label, children, open, onToggle, accent = "emerald" }: {
  id: string; label: string; children: React.ReactNode; open: boolean; onToggle: () => void; accent?: string;
}) {
  const accentColor = accent === "amber" ? "var(--color-amber)" : accent === "blue" ? "var(--color-blue)" : accent === "violet" ? "var(--color-violet)" : "var(--color-emerald)";
  return (
    <div style={{ borderRadius: "var(--radius-md)", overflow: "hidden", marginBottom: "4px", border: `1px solid ${open ? "var(--color-border-strong)" : "var(--color-border)"}`, transition: "border-color 0.2s ease" }}>
      <button
        id={`accordion-${id}`}
        onClick={onToggle}
        style={{ width: "100%", padding: "12px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", background: open ? "var(--color-bg-panel)" : "transparent", border: "none", cursor: "pointer", transition: "background 0.2s ease" }}
        aria-expanded={open}
        aria-controls={`accordion-content-${id}`}
      >
        <span style={{ fontSize: "12px", fontWeight: 600, color: open ? accentColor : "var(--color-text-secondary)", letterSpacing: "0.02em" }}>{label}</span>
        <span style={{ color: "var(--color-text-muted)" }}><ChevronIcon open={open} /></span>
      </button>
      {open && (
        <div id={`accordion-content-${id}`} style={{ padding: "0 14px 14px", animation: "fadeIn 0.2s ease" }}>
          {children}
        </div>
      )}
    </div>
  );
}

function CashFlowCurve({ firstIssuance }: { firstIssuance: number }) {
  const years = 15;
  const w = 360;
  const h = 80;
  const pad = 20;

  // Simplified S-curve: cost-heavy early years, revenue from firstIssuance
  const points = Array.from({ length: years }, (_, i) => {
    const yr = i + 1;
    const cost = Math.exp(-0.4 * yr) * 0.8;
    const rev = yr >= firstIssuance ? Math.min(1, (yr - firstIssuance) * 0.25) : 0;
    const net = rev - cost;
    return { yr, net };
  });

  const minNet = Math.min(...points.map(p => p.net));
  const maxNet = Math.max(...points.map(p => p.net));
  const range = maxNet - minNet || 1;

  const toX = (yr: number) => pad + ((yr - 1) / (years - 1)) * (w - pad * 2);
  const toY = (net: number) => h - pad - ((net - minNet) / range) * (h - pad * 2);

  const zeroY = toY(0);
  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"}${toX(p.yr).toFixed(1)},${toY(p.net).toFixed(1)}`).join(" ");

  return (
    <div style={{ marginTop: "16px" }}>
      <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginBottom: "8px", display: "flex", justifyContent: "space-between" }}>
        <span>Cash-flow curve (illustrative, 15 yr)</span>
        <span style={{ color: "var(--color-emerald)" }}>Break-even ~yr {firstIssuance + 1}</span>
      </div>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: "auto" }}>
        {/* Zero line */}
        <line x1={pad} y1={zeroY} x2={w - pad} y2={zeroY} stroke="rgba(255,255,255,0.08)" strokeWidth="1" strokeDasharray="3,3" />
        {/* Negative fill */}
        <path d={`${pathD} L${toX(years)},${zeroY} L${toX(1)},${zeroY} Z`} fill="rgba(248,113,113,0.08)" />
        {/* Positive fill */}
        <path d={`M${toX(1)},${zeroY} ${points.filter(p => p.net > 0).map(p => `L${toX(p.yr).toFixed(1)},${toY(p.net).toFixed(1)}`).join(" ")} L${toX(years)},${zeroY} Z`} fill="rgba(52,211,153,0.12)" />
        {/* Line */}
        <path d={pathD} fill="none" stroke="var(--color-emerald)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          style={{ strokeDasharray: 1000, strokeDashoffset: 0, animation: "drawLine 1.5s var(--ease-smooth) forwards" }} />
        {/* First issuance marker */}
        <line x1={toX(firstIssuance)} y1={pad} x2={toX(firstIssuance)} y2={h - pad} stroke="var(--color-emerald)" strokeWidth="1" strokeDasharray="2,2" opacity="0.5" />
      </svg>
    </div>
  );
}

function MessageBubble({ msg, isNew }: { msg: Message; isNew: boolean }) {
  const isUser = msg.role === "user";
  const timeString = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Just now";

  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: "24px",
      animation: isNew ? (isUser ? "slideInRight 0.3s ease" : "slideInLeft 0.3s ease") : "none",
    }}>
      {!isUser && (
        <div style={{ width: "36px", height: "36px", borderRadius: "50%", background: "#f0f4f1", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginRight: "12px", color: "var(--color-emerald-deep)" }}>
          <LeafIcon />
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start', maxWidth: "70%" }}>
        <div style={{
          padding: "16px",
          width: "fit-content",
          borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
          background: isUser ? "#e8f2ec" : "#ffffff",
          border: isUser ? "none" : "1px solid rgba(229, 231, 235, 0.5)",
          boxShadow: isUser ? "none" : "0 2px 10px rgba(0,0,0,0.02)",
        }}>
          <p style={{ fontSize: "14px", lineHeight: 1.65, color: isUser ? "#1e563b" : "var(--color-text-primary)", whiteSpace: "pre-wrap", marginBottom: "8px" }}>
            {msg.content.split(/(\*\*.*?\*\*)/g).map((part, index) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={index} style={{ fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
              }
              return <span key={index}>{part}</span>;
            })}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: isUser ? 'flex-end' : 'flex-start', gap: '4px' }}>
            <span style={{ fontSize: '11px', color: isUser ? '#5b8c72' : 'var(--color-text-muted)' }}>{timeString}</span>
            {isUser && <span style={{ color: 'var(--color-emerald)', fontSize: '14px', marginLeft: '2px', lineHeight: 1 }}>✔✔</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

function EligibilityModal({ onClose, onSubmit }: { onClose: () => void, onSubmit: (data: any) => void }) {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [schema, setSchema] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/eligibility-form`)
      .then(res => res.json())
      .then(data => {
        // If there's no schema setup yet, we can provide a fallback or just use the data
        if (!data || !data.steps || data.steps.length === 0) {
          // Provide a fallback schema if backend is empty during development
          setSchema({
             steps: [
               { step_id: "s1", title: "Where is your land located?", description: "Please provide the state and district.", fields: [
                 { field_id: "state", label: "State", type: "text", required: true },
                 { field_id: "district", label: "District", type: "text", required: true }
               ]}
             ]
          });
        } else {
          setSchema(data);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load schema", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ background: "var(--color-bg-panel)", padding: "32px", borderRadius: "var(--radius-xl)" }}>Loading form...</div>
      </div>
    );
  }

  const steps = schema.steps;
  const currentStep = steps[step - 1];

  const handleNext = () => {
    // Validate current step
    for (const field of currentStep.fields) {
      if (field.required && !formData[field.field_id]) {
        return alert(`Please fill out: ${field.label}`);
      }
    }

    if (step < steps.length) {
      setStep(step + 1);
    } else {
      // Submission
      // Format number fields
      const submission = { ...formData };
      for (const s of steps) {
        for (const f of s.fields) {
          if (f.type === "number" && submission[f.field_id]) {
            submission[f.field_id] = parseFloat(submission[f.field_id]) || 0;
          }
        }
      }
      onSubmit(submission);
    }
  };

  const updateField = (id: string, val: any) => {
    setFormData(prev => ({ ...prev, [id]: val }));
  };

  return (
    <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(4px)" }}>
      <div style={{ background: "var(--color-bg-panel)", borderRadius: "var(--radius-xl)", width: "100%", maxWidth: "500px", padding: "32px", position: "relative", boxShadow: "var(--shadow-panel)", border: "1px solid var(--color-border)" }}>
        <button onClick={onClose} style={{ position: "absolute", top: "20px", right: "20px", background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: "20px" }}>&times;</button>

        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div style={{ width: "48px", height: "48px", borderRadius: "50%", background: "var(--color-emerald-glow)", border: "1px solid var(--color-emerald-dim)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-emerald)", margin: "0 auto 16px" }}>
            <LeafIcon />
          </div>
          <h2 style={{ fontSize: "20px", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: "8px" }}>Check Your Land Eligibility</h2>
          <p style={{ fontSize: "13px", color: "var(--color-text-secondary)" }}>Answer a few quick questions and get a preliminary assessment of your land's eligibility for carbon credits.</p>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px", position: "relative" }}>
          <div style={{ position: "absolute", top: "50%", left: "15px", right: "15px", height: "2px", background: "var(--color-bg-deep)", zIndex: 0 }} />
          {steps.map((_: any, idx: number) => {
            const i = idx + 1;
            return (
              <div key={i} style={{ width: "30px", height: "30px", borderRadius: "50%", background: i <= step ? "var(--color-emerald)" : "var(--color-bg-deep)", border: `2px solid ${i <= step ? "var(--color-emerald)" : "var(--color-border)"}`, color: i <= step ? "#fff" : "var(--color-text-muted)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "12px", fontWeight: 600, position: "relative", zIndex: 1, transition: "all 0.3s ease" }}>
                {i}
              </div>
            );
          })}
        </div>
        <div style={{ textAlign: "center", fontSize: "11px", color: "var(--color-text-muted)", marginBottom: "24px", fontWeight: 600, textTransform: "uppercase" }}>Step {step} of {steps.length}</div>

        <div style={{ minHeight: "180px" }}>
          <div>
            <h3 style={{ fontSize: "15px", fontWeight: 600, marginBottom: "8px" }}>{currentStep.title}</h3>
            {currentStep.description && <p style={{ fontSize: "12px", color: "var(--color-text-secondary)", marginBottom: "16px" }}>{currentStep.description}</p>}
            
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {currentStep.fields.map((f: any) => (
                <div key={f.field_id}>
                  <label style={{ display: "block", fontSize: "11px", color: "var(--color-text-muted)", marginBottom: "4px" }}>
                    {f.label} {f.required && <span style={{ color: "var(--color-amber)" }}>*</span>}
                  </label>
                  
                  {f.type === "select" ? (
                    <select 
                      value={formData[f.field_id] || ""} 
                      onChange={e => updateField(f.field_id, e.target.value)} 
                      style={{ width: "100%", padding: "10px", background: "var(--color-bg-input)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)", outline: "none" }}
                    >
                      <option value="">Select an option</option>
                      {(f.options || []).map((opt: string) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  ) : f.type === "boolean" ? (
                    <select 
                      value={formData[f.field_id] || ""} 
                      onChange={e => updateField(f.field_id, e.target.value === "true")} 
                      style={{ width: "100%", padding: "10px", background: "var(--color-bg-input)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)", outline: "none" }}
                    >
                      <option value="">Select an option</option>
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  ) : (
                    <input 
                      type={f.type === "number" ? "number" : "text"} 
                      placeholder={f.placeholder || ""} 
                      value={formData[f.field_id] || ""} 
                      onChange={e => updateField(f.field_id, e.target.value)} 
                      style={{ width: "100%", padding: "10px", background: "var(--color-bg-input)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)", outline: "none" }} 
                    />
                  )}
                  {f.description && <div style={{ fontSize: "10px", color: "var(--color-text-muted)", marginTop: "4px" }}>{f.description}</div>}
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: "12px", padding: "12px", background: "var(--color-emerald-glow)", border: "1px solid var(--color-emerald-dim)", borderRadius: "var(--radius-sm)", marginTop: "24px" }}>
            <div style={{ color: "var(--color-emerald)", fontSize: "18px" }}>🛡️</div>
            <div>
              <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-emerald)", marginBottom: "2px" }}>Your information is safe with us</div>
              <div style={{ fontSize: "11px", color: "var(--color-emerald)" }}>We use this information only for eligibility assessment and never share it with third parties.</div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: "12px", marginTop: "24px", flexDirection: "row-reverse" }}>
          <button onClick={handleNext} style={{ flex: 1, padding: "12px", background: "var(--color-emerald)", color: "#000", border: "none", borderRadius: "var(--radius-sm)", fontWeight: 600, cursor: "pointer", transition: "all 0.2s ease" }}>
            {step === steps.length ? "Submit Assessment" : "Next →"}
          </button>
          {step > 1 && (
            <button onClick={() => setStep(step - 1)} style={{ padding: "12px 24px", background: "transparent", color: "var(--color-text-secondary)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", fontWeight: 500, cursor: "pointer" }}>
              Back
            </button>
          )}
          {step === 1 && (
            <button onClick={onClose} style={{ padding: "12px 24px", background: "transparent", color: "var(--color-text-secondary)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", fontWeight: 500, cursor: "pointer" }}>
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function SplashScreen({ onDismiss }: { onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 5000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div
      onClick={onDismiss}
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        background: "var(--color-bg-deep)", zIndex: 9999,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        animation: "fadeOut 0.5s ease 4.5s forwards", cursor: "pointer"
      }}
    >
      <div style={{ width: "80px", height: "80px", borderRadius: "20px", background: "var(--color-emerald-glow)", border: "1px solid var(--color-emerald-dim)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-emerald)", marginBottom: "24px", animation: "pulse-emerald 2s infinite" }}>
        <LeafIcon />
      </div>
      <h1 style={{ fontSize: "32px", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: "12px", animation: "slideInRight 0.5s ease" }}>EnviroWealth</h1>
      <p style={{ fontSize: "16px", color: "var(--color-text-secondary)", animation: "slideInLeft 0.5s ease" }}>CARBON ELIGIBILITY ASSESSOR</p>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! I'm EnviroWealth's carbon credit eligibility consultant.\n\nI'll walk you through a quick eligibility screening for your land. It takes 5–7 minutes and covers the key requirements of Indian carbon methodologies (CCTS, VM0047, Gold Standard, Plan Vivo).\n\nShall we begin? Tell me a bit about your land — or draw it on the map panel →",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [uiState, setUiState] = useState<UIState>({});
  const [memo, setMemo] = useState<Memo | null>(null);
  const [showMap, setShowMap] = useState(false);
  const [showEligibilityModal, setShowEligibilityModal] = useState(false);
  const [newMessageIndex, setNewMessageIndex] = useState<number>(-1);
  const [showSplash, setShowSplash] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [audioVolumes, setAudioVolumes] = useState<number[]>(new Array(60).fill(3));
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    if (isListening) {
      navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        streamRef.current = stream;
        const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
        const audioCtx = new AudioContext();
        audioContextRef.current = audioCtx;

        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64; // Small fftSize for fewer frequency bins
        analyserRef.current = analyser;

        const source = audioCtx.createMediaStreamSource(stream);
        source.connect(analyser);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        const updateVolumes = () => {
          analyser.getByteFrequencyData(dataArray);
          // We have 60 bars. Let's map the frequency data to heights (min 3px, max 24px)
          const newVolumes = [];
          for (let i = 0; i < 60; i++) {
            // Map index to frequency bin, slightly smoothing it out
            const binIndex = Math.floor((i / 60) * (analyser.frequencyBinCount * 0.5));
            const value = dataArray[binIndex] || 0;
            // Normalize value (0-255) to height (3-24)
            const height = 3 + (value / 255) * 21;
            newVolumes.push(height);
          }
          setAudioVolumes(newVolumes);
          animationFrameRef.current = requestAnimationFrame(updateVolumes);
        };

        updateVolumes();
      }).catch(err => {
        console.error("Microphone access denied or error:", err);
        // Fallback to straight line if denied
        setAudioVolumes(new Array(60).fill(3));
      });
    } else {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (audioContextRef.current) audioContextRef.current.close();
      if (streamRef.current) streamRef.current.getTracks().forEach(track => track.stop());
      setAudioVolumes(new Array(60).fill(3));
    }

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (audioContextRef.current) audioContextRef.current.close();
      if (streamRef.current) streamRef.current.getTracks().forEach(track => track.stop());
    };
  }, [isListening]);

  const { token, user, logout } = useAuthStore();

  useEffect(() => {
    // Check splash
    if (!sessionStorage.getItem("splashShown")) {
      setShowSplash(true);
      sessionStorage.setItem("splashShown", "true");
    }
  }, []);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMsg: Message = { role: "user", content: content.trim(), timestamp: new Date() };
    setMessages(prev => {
      setNewMessageIndex(prev.length);
      return [...prev, userMsg];
    });
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId, message: content.trim() }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error ${response.status}: ${errorText}`);
      }

      const data = await response.json();

      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
      }

      if (data.ui_state) {
        setUiState(data.ui_state);
        if (data.ui_state.action === 'SHOW_ELIGIBILITY_MODAL') {
          setShowEligibilityModal(true);
        }
      }

      if (data.verdict) {
        setMemo(data.verdict as Memo);
      }

      if (data.reply) {
        const assistantMsg: Message = { role: "assistant", content: data.reply, timestamp: new Date() };
        setMessages(prev => {
          setNewMessageIndex(prev.length);
          return [...prev, assistantMsg];
        });
      }
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : "Unknown error";
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `I'm having trouble connecting right now. Please try again.\n\n_Error: ${errMsg}_`,
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [sessionId, isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  const isScreening = uiState.stage === "screening";
  const verdictReady = !!memo;
  const progress = uiState.progress ?? 0;

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--color-bg-deep)", fontFamily: "var(--font-sans)" }}>
      {token && <Sidebar onSelectSession={(id: string) => setSessionId(id)} currentSessionId={sessionId} onNewAssessment={() => { setSessionId(null); setMessages([{ role: "assistant", content: "Let's start a new assessment.", timestamp: new Date() }]); setUiState({}); setMemo(null); }} />}

      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <header style={{ flexShrink: 0, borderBottom: "1px solid var(--color-border)", background: "var(--color-bg-base)", padding: "0 24px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", height: "64px", gap: "12px" }}>
            {isScreening && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "5px 12px", background: "var(--color-emerald-deep)", border: "1px solid var(--color-border-strong)", borderRadius: "var(--radius-full)", animation: "fadeIn 0.3s ease" }}>
                <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--color-emerald)", animation: "pulse-emerald 1.5s infinite" }} />
                <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-emerald)", letterSpacing: "0.06em" }}>
                  SCREENING · {Math.round(progress * 100)}%
                </span>
              </div>
            )}
            <button
              id="toggle-map-btn"
              onClick={() => setShowMap(v => !v)}
              style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 16px", background: "var(--color-bg-panel)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: "13px", fontWeight: 500, color: "var(--color-text-primary)", transition: "all 0.2s ease", boxShadow: "var(--shadow-card)" }}
            >
              <MapIcon />
              <span>Map</span>
            </button>
            <span style={{ fontSize: "12px", color: "var(--color-text-muted)", padding: "8px 16px", background: "#f3f4f6", border: "none", borderRadius: "var(--radius-full)" }}>Screening only — not legal/financial advice</span>

            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: '8px', cursor: 'pointer' }}>
              <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--color-emerald-deep)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: '14px' }}>C</div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" color="var(--color-text-primary)"><polyline points="6 9 12 15 18 9" /></svg>
            </div>

            {user && (
              <button onClick={logout} style={{ padding: '6px 12px', background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: '12px', marginLeft: '8px' }}>Logout</button>
            )}
          </div>
        </header>
        {/* ── Body ───────────────────────────────────────────────────────────── */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden", width: "100%" }}>

          {/* Chat panel */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
            <div ref={chatContainerRef} style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>

              {/* Progress bar */}
              {isScreening && uiState.filled_fields !== undefined && (
                <ProgressBar
                  progress={progress}
                  filledFields={uiState.filled_fields}
                  totalFields={uiState.total_fields ?? 6}
                  currentField={uiState.current_field}
                />
              )}

              {/* Messages */}
              {messages.map((msg, i) => {
                if (msg.role === 'user' && msg.content.includes('"eligibility_form"')) {
                  return (
                    <div key={i} style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
                      <div style={{ background: 'var(--color-bg-panel)', border: '1px solid var(--color-emerald-dim)', borderRadius: '16px 16px 4px 16px', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <LeafIcon />
                        <span style={{ fontSize: '13px', color: 'var(--color-emerald)' }}>Submitted Eligibility Assessment Form</span>
                      </div>
                    </div>
                  );
                }
                return <MessageBubble key={i} msg={msg} isNew={i === newMessageIndex} />;
              })}

              {/* Typing indicator */}
              {isLoading && <TypingIndicator />}

              {/* Verdict card */}
              {verdictReady && memo && (
                <div style={{ marginTop: "20px", animation: "revealUp 0.5s var(--ease-spring)" }}>
                  <VerdictCard memo={memo} />
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div style={{ flexShrink: 0, padding: "24px", background: "var(--color-bg-base)", display: "flex", flexDirection: "column", alignItems: "center", position: "relative" }}>

              {/* Input Wrapper */}
              <div style={{ position: "relative", width: "100%", maxWidth: "800px", display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", width: "100%", background: "white", borderRadius: "99px", padding: "8px 16px", boxShadow: "0 2px 10px rgba(0,0,0,0.05)", border: "1px solid rgba(229,231,235,0.8)", minHeight: "56px" }}>
                  
                  {isListening ? (
                    <>
                      <button style={{ width: "36px", height: "36px", display: "flex", alignItems: "center", justifyContent: "center", color: "#d1d5db", background: "transparent", border: "none" }}>
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>
                      </button>
                      
                      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '0 16px', overflow: 'hidden' }}>
                        {/* Audio visualizer */}
                        {audioVolumes.map((h, i) => (
                          <div key={i} style={{ 
                            width: '3px', 
                            height: `${h}px`, 
                            background: i > 40 ? '#d1d5db' : '#9ca3af', 
                            borderRadius: '2px', 
                            transition: 'height 0.05s ease'
                          }} />
                        ))}
                      </div>
                      
                      <button onClick={() => setIsListening(false)} style={{ width: "32px", height: "32px", borderRadius: "50%", background: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center", color: "#4b5563", border: "none", cursor: "pointer", marginRight: "8px" }}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                      </button>
                      <button onClick={() => setIsListening(false)} style={{ width: "36px", height: "36px", borderRadius: "50%", background: "white", border: "2px solid black", display: "flex", alignItems: "center", justifyContent: "center", color: "black", cursor: "pointer" }}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                      </button>
                    </>
                  ) : (
                    <>
                      <button style={{ width: "36px", height: "36px", display: "flex", alignItems: "center", justifyContent: "center", color: "#6b7280", background: "transparent", border: "none", cursor: "pointer" }}>
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>
                      </button>
                      
                      <div style={{ flex: 1, position: "relative" }}>
                        <textarea
                          ref={inputRef}
                          id="chat-input"
                          value={input}
                          onChange={handleTextareaChange}
                          onKeyDown={handleKeyDown}
                          disabled={isLoading}
                          placeholder=""
                          rows={1}
                          style={{
                            width: "100%", resize: "none", background: "transparent", border: "none",
                            padding: "8px 12px", fontSize: "15px", color: "var(--color-text-primary)", outline: "none",
                            lineHeight: 1.5, maxHeight: "120px", fontFamily: "var(--font-sans)",
                          }}
                        />
                      </div>
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        
                        <button onClick={() => setIsListening(true)} style={{ width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", color: "#374151", background: "transparent", border: "none", cursor: "pointer" }}>
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
                        </button>
                        
                        <button onClick={() => sendMessage(input)} disabled={isLoading || !input.trim()} style={{ width: "36px", height: "36px", borderRadius: "50%", background: input.trim() && !isLoading ? "black" : "black", border: "none", cursor: input.trim() && !isLoading ? "pointer" : "not-allowed", display: "flex", alignItems: "center", justifyContent: "center", color: "white" }}>
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Map panel */}
          {showMap && (
            <div style={{ width: "40%", minWidth: "320px", maxWidth: "520px", borderLeft: "1px solid var(--color-border)", background: "var(--color-bg-panel)", display: "flex", flexDirection: "column", animation: "slideInRight 0.3s ease" }}>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--color-border)" }}>
                <h3 style={{ fontSize: "13px", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: "2px" }}>Draw Your Land Parcel</h3>
                <p style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>Use the polygon tool to outline your land. Satellite data (tree cover, rainfall zone) will be fetched automatically.</p>
              </div>
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--color-bg-deep)", padding: "24px" }}>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "48px", marginBottom: "12px", opacity: 0.3 }}>🗺️</div>
                  <p style={{ fontSize: "12px", color: "var(--color-text-muted)", lineHeight: 1.5 }}>
                    Map integration requires a Mapbox/MapLibre API key.<br />
                    Configure <code style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--color-emerald-dim)" }}>NEXT_PUBLIC_MAPBOX_TOKEN</code> in your <code style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--color-emerald-dim)" }}>.env</code> file.
                  </p>
                </div>
              </div>
            </div>
          )}

        </div>

        {showEligibilityModal && (
          <EligibilityModal
            onClose={() => setShowEligibilityModal(false)}
            onSubmit={(data) => {
              setShowEligibilityModal(false);
              sendMessage(JSON.stringify({ eligibility_form: data }));
            }}
          />
        )}

        {showSplash && <SplashScreen onDismiss={() => setShowSplash(false)} />}
        {!showSplash && !token && <AuthModal />}
      </div>
    </div>
  );
}
