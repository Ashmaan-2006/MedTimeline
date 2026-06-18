import type {
  PatientGraphEntity,
  PatientGraphEvidenceChunk,
  PatientGraphRelationship,
  PatientGraphSummary,
  TimelineEvent,
} from "@/lib/api";

type ClinicalGraphPanelProps = {
  entities: PatientGraphEntity[];
  evidenceChunks: PatientGraphEvidenceChunk[];
  relationships: PatientGraphRelationship[];
  summary: PatientGraphSummary | null;
  timelineEvents: TimelineEvent[];
};

const ENTITY_GROUPS = [
  { label: "Symptoms", graphLabel: "Symptom" },
  { label: "Medications", graphLabel: "Medication" },
  { label: "Diagnoses", graphLabel: "Diagnosis" },
  { label: "Labs", graphLabel: "LabTest" },
  { label: "Findings", graphLabel: "ECGFinding" },
];

function formatRelationshipType(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function formatDateTime(value: string | null) {
  if (value === null) {
    return "Undated";
  }

  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function topEntitiesForLabel(entities: PatientGraphEntity[], label: string) {
  return entities
    .filter((entity) => entity.label === label)
    .sort((left, right) => right.mention_count - left.mention_count)
    .slice(0, 5);
}

function relationshipKey(relationship: PatientGraphRelationship) {
  return [
    relationship.source_label,
    relationship.source_name,
    relationship.relationship_type,
    relationship.target_label,
    relationship.target_name,
    relationship.source_chunk_id ?? "no-chunk",
  ].join("|");
}

export function ClinicalGraphPanel({
  entities,
  evidenceChunks,
  relationships,
  summary,
  timelineEvents,
}: ClinicalGraphPanelProps) {
  const hasGraphData = entities.length > 0 || relationships.length > 0 || evidenceChunks.length > 0;
  const connectedEvents = timelineEvents.slice(0, 6);

  return (
    <section className="panel graph-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Clinical Graph</h2>
          <p className="panel-kicker">
            Inspect extracted clinical entities, relationships, timeline context, and source
            snippets.
          </p>
        </div>
      </div>

      {summary !== null ? (
        <div className="graph-metric-row" aria-label="Clinical graph metrics">
          <div className="graph-metric">
            <span>Entities</span>
            <strong>{summary.entity_count}</strong>
          </div>
          <div className="graph-metric">
            <span>Relationships</span>
            <strong>{summary.relationship_count}</strong>
          </div>
          <div className="graph-metric">
            <span>Chunks</span>
            <strong>{summary.chunk_count}</strong>
          </div>
        </div>
      ) : null}

      {hasGraphData ? (
        <>
          <div className="graph-entity-grid">
            {ENTITY_GROUPS.map((group) => {
              const groupEntities = topEntitiesForLabel(entities, group.graphLabel);
              return (
                <article className="graph-entity-card" key={group.graphLabel}>
                  <h3>{group.label}</h3>
                  {groupEntities.length > 0 ? (
                    <ul>
                      {groupEntities.map((entity) => (
                        <li key={`${entity.label}-${entity.normalized_name}`}>
                          <span>{entity.name ?? entity.normalized_name}</span>
                          <small>
                            {entity.mention_count} mention
                            {entity.mention_count === 1 ? "" : "s"}
                          </small>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>No extracted {group.label.toLowerCase()} yet.</p>
                  )}
                </article>
              );
            })}
          </div>

          <div className="graph-section">
            <div className="graph-section-header">
              <h3>Relationship Evidence</h3>
              <span>{relationships.length} relationship{relationships.length === 1 ? "" : "s"}</span>
            </div>
            {relationships.length > 0 ? (
              <div className="graph-table-wrap">
                <table className="graph-table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th>Relationship</th>
                      <th>Target</th>
                      <th>Evidence</th>
                      <th>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {relationships.map((relationship) => (
                      <tr key={relationshipKey(relationship)}>
                        <td>
                          <strong>{relationship.source_name}</strong>
                          <span>{relationship.source_label}</span>
                        </td>
                        <td>{formatRelationshipType(relationship.relationship_type)}</td>
                        <td>
                          <strong>{relationship.target_name}</strong>
                          <span>{relationship.target_label}</span>
                        </td>
                        <td>{relationship.evidence ?? "No evidence snippet stored."}</td>
                        <td>
                          {relationship.confidence !== null
                            ? `${Math.round(relationship.confidence * 100)}%`
                            : "Unknown"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state graph-empty-state">
                Entity relationships will appear after graph extraction finds connected clinical
                facts.
              </div>
            )}
          </div>

          <div className="graph-lower-grid">
            <div className="graph-section">
              <div className="graph-section-header">
                <h3>Connected Timeline Events</h3>
                <span>{connectedEvents.length} shown</span>
              </div>
              {connectedEvents.length > 0 ? (
                <ul className="graph-event-list">
                  {connectedEvents.map((event) => (
                    <li key={event.id}>
                      <span>{event.event_type}</span>
                      <strong>{event.title}</strong>
                      <small>{formatDateTime(event.occurred_at)}</small>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="empty-state graph-empty-state">
                  Timeline events connected to graph context will appear here.
                </div>
              )}
            </div>

            <div className="graph-section">
              <div className="graph-section-header">
                <h3>Source Snippets</h3>
                <span>{evidenceChunks.length} snippet{evidenceChunks.length === 1 ? "" : "s"}</span>
              </div>
              {evidenceChunks.length > 0 ? (
                <div className="graph-snippet-list">
                  {evidenceChunks.slice(0, 8).map((chunk) => (
                    <article className="graph-snippet" key={chunk.chunk_id}>
                      <div>
                        <strong>{chunk.filename ?? "Source document"}</strong>
                        <span>
                          Chunk {chunk.chunk_index !== null ? chunk.chunk_index + 1 : "unknown"} -
                          {" "}
                          {formatDateTime(chunk.created_at)}
                        </span>
                      </div>
                      <p>{chunk.evidence ?? chunk.content}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state graph-empty-state">
                  Source snippets will appear once entities are linked back to document chunks.
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state graph-empty-state">
          The clinical graph will populate after completed documents are processed into entities and
          relationships.
        </div>
      )}
    </section>
  );
}
