-- =============================================================================
-- Carbon Credit Eligibility Chatbot — Database Initialization
-- PostgreSQL 16 with pgvector + PostGIS extensions
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS postgis;         -- spatial data
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- fuzzy text matching
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- UUID generation

-- =============================================================================
-- LLM PROVIDER CONFIGURATION (Admin Panel managed, global)
-- =============================================================================
CREATE TABLE IF NOT EXISTS llm_provider_configs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,   -- only one row active at a time
    is_fallback     BOOLEAN NOT NULL DEFAULT FALSE,   -- one row as fallback
    provider        VARCHAR(20) NOT NULL,             -- claude | openai | groq | gemini
    model_name      VARCHAR(100) NOT NULL,
    api_key_enc     TEXT NOT NULL,                   -- encrypted at application layer
    extra_params    JSONB DEFAULT '{}',              -- temperature, max_tokens, etc.
    last_tested_at  TIMESTAMPTZ,
    last_test_ok    BOOLEAN,
    last_test_ms    INTEGER,                         -- latency of last health check
    updated_by      VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure exactly one active + one fallback config at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_active ON llm_provider_configs (is_active) WHERE is_active = TRUE;
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_fallback ON llm_provider_configs (is_fallback) WHERE is_fallback = TRUE;

-- =============================================================================
-- KNOWLEDGE CORPUS (RAG documents)
-- =============================================================================
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           VARCHAR(500) NOT NULL,
    version         VARCHAR(50),
    publication_date DATE,
    effective_date  DATE,
    jurisdiction    VARCHAR(100),                    -- India | global | state:Maharashtra
    doc_type        VARCHAR(50),                     -- methodology | regulation | guidance
    standard_body   VARCHAR(100),                    -- Verra | CCTS | MoEFCC | GCP
    file_path       TEXT,                            -- stored on disk
    file_hash       VARCHAR(64),                     -- SHA-256 for dedup
    retrieval_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    superseded_by   UUID REFERENCES knowledge_documents(id),
    source_url      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    doc_summary     TEXT,                            -- prepended document-level summary
    embedding       vector(384),                   -- dimension set for all-MiniLM-L6-v2
    metadata        JSONB DEFAULT '{}',              -- section, clause, page_num, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- HNSW index for approximate nearest-neighbour search (fast retrieval)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Full-text index for BM25 (hybrid search)
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON knowledge_chunks
    USING GIN (to_tsvector('english', content));

-- =============================================================================
-- ASSESSMENTS (intake + gate results + verdicts)
-- =============================================================================
CREATE TABLE IF NOT EXISTS assessment_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_token   VARCHAR(128) UNIQUE NOT NULL,    -- anonymous session
    tier            INTEGER NOT NULL DEFAULT 1,       -- 1, 2, or 3
    intake_data     JSONB DEFAULT '{}',               -- collected field answers
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gate_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    gate_id         VARCHAR(20) NOT NULL,            -- gate_1 … gate_10
    status          VARCHAR(30) NOT NULL,            -- pass | fail_structural | flag | insufficient_info
    reason          TEXT NOT NULL,
    redirect        TEXT,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assessments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    verdict         VARCHAR(40) NOT NULL,            -- 6 categories
    confidence      VARCHAR(10),                    -- high | medium | low
    confidence_reason TEXT,
    knockout_gate   VARCHAR(20),
    flags           JSONB DEFAULT '[]',
    indicative_data JSONB DEFAULT '{}',             -- credits, revenue, timeline ranges
    what_we_could_not_check JSONB DEFAULT '[]',
    next_steps      JSONB DEFAULT '[]',
    alternatives    JSONB DEFAULT '[]',
    raw_gate_results JSONB DEFAULT '[]',
    llm_model_used  VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- LEAD MANAGEMENT
-- =============================================================================
CREATE TABLE IF NOT EXISTS leads (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID REFERENCES assessment_sessions(id),
    assessment_id   UUID REFERENCES assessments(id),
    name            VARCHAR(200),
    mobile          VARCHAR(20),
    email           VARCHAR(200),
    state           VARCHAR(100),
    preferred_contact VARCHAR(20),
    consent_given   BOOLEAN NOT NULL DEFAULT FALSE,
    lead_score      VARCHAR(20),                    -- Cold | Qualified | Hot
    score_reason    JSONB DEFAULT '{}',
    status          VARCHAR(30) DEFAULT 'new',      -- new | contacted | converted | rejected
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(lead_score, status);

-- =============================================================================
-- AUDIT LOG (immutable record of all eligibility verdicts)
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type      VARCHAR(50) NOT NULL,
    session_id      UUID,
    assessment_id   UUID,
    payload         JSONB DEFAULT '{}',
    ip_hash         VARCHAR(64),                    -- hashed for privacy
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_event ON audit_logs(event_type, created_at);
