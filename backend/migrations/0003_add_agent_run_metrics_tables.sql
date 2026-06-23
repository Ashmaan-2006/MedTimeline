CREATE TABLE IF NOT EXISTS agent_eval_results (
    id UUID PRIMARY KEY,
    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    evaluator_name VARCHAR(128) NOT NULL,
    eval_score DOUBLE PRECISION,
    latency_ms INTEGER,
    error_count INTEGER NOT NULL DEFAULT 0,
    details_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_agent_eval_results_agent_run_id
    ON agent_eval_results(agent_run_id);

CREATE INDEX IF NOT EXISTS ix_agent_eval_results_evaluator_name
    ON agent_eval_results(evaluator_name);

CREATE TABLE IF NOT EXISTS llm_call_metrics (
    id UUID PRIMARY KEY,
    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    step_name VARCHAR(128),
    model_name VARCHAR(255),
    latency_ms INTEGER,
    tokens_input INTEGER,
    tokens_output INTEGER,
    error_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_llm_call_metrics_agent_run_id
    ON llm_call_metrics(agent_run_id);

CREATE INDEX IF NOT EXISTS ix_llm_call_metrics_step_name
    ON llm_call_metrics(step_name);

CREATE INDEX IF NOT EXISTS ix_llm_call_metrics_model_name
    ON llm_call_metrics(model_name);

CREATE TABLE IF NOT EXISTS retrieval_metrics (
    id UUID PRIMARY KEY,
    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    retrieval_type VARCHAR(64) NOT NULL,
    latency_ms INTEGER,
    retrieved_chunk_count INTEGER NOT NULL DEFAULT 0,
    graph_entity_count INTEGER NOT NULL DEFAULT 0,
    graph_relationship_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_retrieval_metrics_agent_run_id
    ON retrieval_metrics(agent_run_id);

CREATE INDEX IF NOT EXISTS ix_retrieval_metrics_retrieval_type
    ON retrieval_metrics(retrieval_type);
