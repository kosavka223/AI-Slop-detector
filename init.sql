CREATE TABLE IF NOT EXISTS verdicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id VARCHAR(255) NOT NULL,
    overall_risk VARCHAR(50) NOT NULL,
    ai_assistance_score FLOAT NOT NULL,
    classification VARCHAR(100) NOT NULL,
    cluster_id VARCHAR(64),
    full_verdict JSONB NOT NULL,
    decided_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_verdicts_email ON verdicts (email_id);
CREATE INDEX IF NOT EXISTS idx_verdicts_cluster ON verdicts (cluster_id);
