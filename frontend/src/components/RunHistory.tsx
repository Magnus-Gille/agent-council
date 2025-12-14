import { useState, useEffect } from 'react';
import type { Run } from '../types';
import { listRuns, deleteRun } from '../api';

interface Props {
  onSelect: (runId: number) => void;
  currentRunId?: number;
  refreshTrigger: number;
}

export function RunHistory({ onSelect, currentRunId, refreshTrigger }: Props) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  const loadRuns = () => {
    setLoading(true);
    listRuns()
      .then(setRuns)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadRuns();
  }, [refreshTrigger]);

  const handleDelete = async (e: React.MouseEvent, runId: number) => {
    e.stopPropagation();
    if (confirm('Delete this run?')) {
      await deleteRun(runId);
      loadRuns();
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'complete':
        return 'status-complete';
      case 'failed':
        return 'status-failed';
      case 'generating_answers':
      case 'evaluating':
        return 'status-running';
      default:
        return 'status-pending';
    }
  };

  if (loading && runs.length === 0) {
    return <div className="run-history loading">Loading history...</div>;
  }

  return (
    <div className="run-history">
      <h3>History</h3>
      {runs.length === 0 ? (
        <div className="no-runs">No previous runs</div>
      ) : (
        <div className="runs-list">
          {runs.map((run) => (
            <div
              key={run.id}
              className={`run-item ${run.id === currentRunId ? 'selected' : ''}`}
              onClick={() => onSelect(run.id)}
            >
              <div className="run-question">{run.question.slice(0, 50)}...</div>
              <div className="run-meta">
                <span className={`status ${getStatusClass(run.status)}`}>{run.status}</span>
                <span className="date">{formatDate(run.created_at)}</span>
                <button
                  className="delete-btn"
                  onClick={(e) => handleDelete(e, run.id)}
                  title="Delete run"
                >
                  ×
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
