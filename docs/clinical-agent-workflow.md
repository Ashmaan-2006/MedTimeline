# Clinical Agent Workflow

MedGraph AI uses a LangGraph workflow to turn a patient-specific question into a grounded, cited response. The workflow is designed for clinical record review, not diagnosis.

## Workflow Diagram

```text
User question
  |
  v
Intent Classifier
  |
  v
Evidence Planner
  |
  +---------------------+
  |                     |
  v                     v
Vector Retriever     Graph Retriever
  |                     |
  +----------+----------+
             |
             v
Timeline Reasoner
  |
  v
Contradiction Checker
  |
  v
Risk Flagger
  |
  v
Grounded Answer Generator
```

Conditional routing keeps the workflow scoped:

- `general_question` skips risk flagging.
- `contradiction_check` can route directly to contradiction checking when timeline evidence is not required.
- `medication_history`, `symptom_progression`, and `lab_trend` use timeline reasoning plus retrieval.
- Evidence planning decides whether vector search, graph search, and timeline reasoning are needed.

## Node Responsibilities

| Node | Responsibility | Main State Inputs | Main State Outputs |
| --- | --- | --- | --- |
| Intent Classifier | Classifies the question into a clinical workflow intent. | `user_question` | `intent`, `required_evidence` |
| Evidence Planner | Decides retrieval needs, target entities, date range, and required evidence. | `user_question`, `intent` | `evidence_plan`, `required_evidence` |
| Vector Retriever | Retrieves semantic evidence from pgvector-backed document chunks. | `patient_id`, `user_question`, `evidence_plan` | `vector_context` |
| Graph Retriever | Retrieves entities, relationships, paths, connected events, and source chunks from Neo4j. | `patient_id`, `evidence_plan` | `graph_context` |
| Timeline Reasoner | Orders relevant evidence chronologically. | `vector_context`, `graph_context` | `timeline_context` |
| Contradiction Checker | Flags conflicting claims across retrieved evidence. | `vector_context`, `graph_context`, `timeline_context` | `contradictions` |
| Risk Flagger | Surfaces review signals such as worsening symptoms, abnormal labs, medication discontinuity, missing follow-up, and conflicting records. | retrieved context and `contradictions` | `risk_flags` |
| Answer Generator | Produces a cautious answer grounded only in retrieved evidence. | `vector_context`, `graph_context`, `timeline_context`, `contradictions`, `risk_flags` | `final_answer`, `citations`, `answer_confidence`, `limitations` |

## State Schema

The shared state lives in `backend/medgraph_api/agents/state.py`.

```python
class ClinicalAgentState(TypedDict):
    patient_id: str
    user_question: str
    intent: str | None
    evidence_plan: dict[str, Any] | None
    required_evidence: list[str]
    vector_context: list[dict[str, Any]]
    graph_context: list[dict[str, Any]]
    timeline_context: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    risk_flags: list[dict[str, Any]]
    final_answer: str | None
    answer_confidence: str | None
    limitations: list[str]
    citations: list[dict[str, Any]]
    errors: list[str]
```

## Example Queries

- `Did symptoms worsen after metoprolol?`
- `What changed before the patient returned to the emergency department?`
- `Are there contradictions about chest pain?`
- `What evidence supports atrial fibrillation?`
- `Did troponin trend upward in March 2026?`
- `What follow-up flags should a clinician review?`

## API Usage

Frontend calls the agent workflow through:

```http
POST /patients/{patient_id}/agent/query
Content-Type: application/json

{
  "question": "Did symptoms worsen after the medication change?"
}
```

Response shape:

```json
{
  "answer": "...",
  "intent": "symptom_progression",
  "timeline": [],
  "contradictions": [],
  "risk_flags": [],
  "citations": [],
  "confidence": "medium",
  "limitations": []
}
```

## Safety Limitations

- The agent is not a diagnosis engine.
- Risk output is framed as signals, follow-up flags, and documentation concerns.
- Every answer includes cautious language and should be reviewed by a qualified clinician.
- Missing records can change the answer.
- Contradictions lower certainty and should trigger human review.
- The system should not be used for emergency triage or autonomous medical decision-making.

Required UI language:

```text
Not medical advice. Review with a qualified clinician.
```

## Testing Coverage

The agent workflow is covered by focused tests:

- Intent classification: `backend/tests/test_intent_classifier.py`
- Evidence planning: `backend/tests/test_evidence_planner.py`
- Vector retrieval node: `backend/tests/test_vector_retriever.py`
- Graph retrieval node: `backend/tests/test_graph_retriever.py`
- Timeline reasoning: `backend/tests/test_timeline_reasoner.py`
- Contradiction detection: `backend/tests/test_contradiction_checker.py`
- Risk flagging: `backend/tests/test_risk_flagger.py`
- Grounded answer generation: `backend/tests/test_answer_generator.py`
- LangGraph workflow routing: `backend/tests/test_clinical_reasoning_graph.py`
- Agent endpoint: `backend/tests/test_agent_api.py`
- Agent trace persistence: `backend/tests/test_agent_run_repository.py`

Run all backend tests:

```powershell
python -m pytest backend\tests
```

## Debugging Agent Runs

Agent executions are persisted in two tables:

- `agent_runs`
- `agent_run_steps`

Useful SQL:

```sql
SELECT
  id,
  patient_id,
  intent,
  status,
  latency_ms,
  model_name,
  token_count,
  error,
  started_at,
  completed_at
FROM agent_runs
ORDER BY started_at DESC
LIMIT 20;
```

```sql
SELECT
  step_name,
  status,
  latency_ms,
  input_summary,
  output_summary
FROM agent_run_steps
WHERE agent_run_id = '<agent-run-id>'
ORDER BY created_at ASC;
```

Debug checklist:

1. Check `agent_runs.status`.
2. If failed, inspect `agent_runs.error`.
3. Review `agent_run_steps` in order to find the last successful node.
4. Compare `input_summary` and `output_summary` to see whether retrieval, graph context, timeline context, contradictions, or risk flags were empty.
5. Re-run the same question after adding documents or rebuilding the graph.

## Known Limitations

- Current local answer generation is deterministic and extractive.
- Risk flagging uses evidence-pattern rules and does not replace clinician judgment.
- Retrieval quality depends on document chunking, embeddings, and graph extraction quality.
- Neo4j relationship quality depends on upstream entity and relationship extraction.
- Token counts are currently estimated from answer length unless a model provider supplies usage metadata.
