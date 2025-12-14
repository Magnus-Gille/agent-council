import type { Answer } from '../types';

interface Props {
  answer: Answer;
  showProvider: boolean;
  rank?: number;
  isWinner?: boolean;
}

export function AnswerCard({ answer, showProvider, rank, isWinner }: Props) {
  return (
    <div className={`answer-card ${answer.error ? 'error' : ''} ${isWinner ? 'winner' : ''}`}>
      <div className="answer-header">
        <div className="answer-label">
          {rank !== undefined && <span className="rank">#{rank + 1}</span>}
          <span className="label">Answer {answer.label}</span>
          {isWinner && <span className="winner-badge">Winner</span>}
        </div>
        {showProvider && (
          <div className="answer-model">
            {answer.provider} / {answer.producer_model}
          </div>
        )}
        <div className="answer-meta">
          <span>{answer.latency_ms}ms</span>
          {answer.tokens_in && answer.tokens_out && (
            <span>
              {answer.tokens_in} in / {answer.tokens_out} out tokens
            </span>
          )}
        </div>
      </div>
      <div className="answer-content">
        {answer.error ? (
          <div className="error-message">Error: {answer.error}</div>
        ) : (
          <pre>{answer.text}</pre>
        )}
      </div>
    </div>
  );
}
