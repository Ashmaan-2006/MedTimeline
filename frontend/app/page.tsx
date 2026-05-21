export default function HomePage() {
  return (
    <>
      <section className="page-header">
        <div>
          <h1 className="page-title">Patient Timeline App</h1>
          <p className="page-description">
            Upload clinical records, extract document text, generate summaries, and assemble a
            longitudinal timeline for each patient.
          </p>
        </div>
      </section>

      <section className="metric-row" aria-label="Workspace metrics">
        <div className="metric">
          <div className="metric-label">Patients</div>
          <div className="metric-value">0</div>
        </div>
        <div className="metric">
          <div className="metric-label">Documents</div>
          <div className="metric-value">0</div>
        </div>
        <div className="metric">
          <div className="metric-label">Timeline Events</div>
          <div className="metric-value">0</div>
        </div>
      </section>

      <section className="workspace-grid">
        <div className="panel">
          <h2 className="panel-title">Recent Patients</h2>
          <div className="empty-state">Patient profile views will appear here.</div>
        </div>
        <div className="panel">
          <h2 className="panel-title">Document Processing</h2>
          <div className="empty-state">Uploaded records and extraction status will appear here.</div>
        </div>
      </section>
    </>
  );
}

