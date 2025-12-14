import type { Review, AggregationResult, Answer } from '../types';

interface Props {
  reviews: Review[];
  aggregation?: AggregationResult;
  answers: Answer[];
}

export function ReviewSection({ reviews, aggregation, answers }: Props) {
  const labelToAnswer = answers.reduce(
    (acc, a) => {
      acc[a.label] = a;
      return acc;
    },
    {} as Record<string, Answer>
  );

  const getWinnerInfo = () => {
    if (!aggregation || aggregation.final_ranking.length === 0) return null;
    const winnerLabel = aggregation.final_ranking[0];
    const winner = labelToAnswer[winnerLabel];
    return { label: winnerLabel, answer: winner };
  };

  const winner = getWinnerInfo();

  return (
    <div className="review-section">
      {/* Winner Banner */}
      {winner && (
        <div className="winner-banner">
          <div className="winner-trophy">🏆</div>
          <div className="winner-info">
            <h2>Winner: Answer {winner.label}</h2>
            {winner.answer && (
              <p className="winner-model">
                {winner.answer.provider} / {winner.answer.producer_model}
              </p>
            )}
          </div>
          <div className="winner-stats">
            <div className="stat">
              <span className="stat-value">{aggregation!.vote_breakdown.borda_totals[winner.label]}</span>
              <span className="stat-label">Borda Points</span>
            </div>
            <div className="stat">
              <span className="stat-value">{aggregation!.vote_breakdown.first_place_votes[winner.label]}</span>
              <span className="stat-label">1st Place Votes</span>
            </div>
            <div className="stat">
              <span className="stat-value">{aggregation!.vote_breakdown.score_averages[winner.label]?.toFixed(1)}</span>
              <span className="stat-label">Avg Score</span>
            </div>
          </div>
        </div>
      )}

      {/* Full Ranking */}
      {aggregation && aggregation.final_ranking.length > 1 && (
        <div className="aggregation-results">
          <h3>Full Ranking</h3>
          <div className="ranking-list">
            {aggregation.final_ranking.map((label, index) => {
              const answer = labelToAnswer[label];
              return (
                <div key={label} className={`ranking-item ${index === 0 ? 'winner' : ''}`}>
                  <span className="position">#{index + 1}</span>
                  <span className="label">Answer {label}</span>
                  {answer && (
                    <span className="model">
                      {answer.provider}/{answer.producer_model}
                    </span>
                  )}
                  <div className="ranking-stats">
                    <span className="borda">
                      {aggregation.vote_breakdown.borda_totals[label]} pts
                    </span>
                    <span className="first-votes">
                      {aggregation.vote_breakdown.first_place_votes[label]} 1st
                    </span>
                    <span className="avg-score">
                      {aggregation.vote_breakdown.score_averages[label]?.toFixed(1)} avg
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Vote Matrix - Who voted for whom */}
      {reviews.length > 0 && (
        <div className="vote-matrix">
          <h3>How Each Model Voted</h3>
          <div className="votes-grid">
            {reviews.map((review) => (
              <div key={review.id} className="vote-row">
                <div className="voter-name">
                  {review.reviewer_provider}/{review.reviewer_model}
                </div>
                <div className="vote-ranking">
                  {review.rank_order.length > 0 ? (
                    review.rank_order.map((label, idx) => (
                      <span key={label} className={`vote-choice ${idx === 0 ? 'first-choice' : ''}`}>
                        {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `${idx + 1}.`} {label}
                      </span>
                    ))
                  ) : (
                    <span className="no-ranking">No ranking provided</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detailed Reviews (collapsible) */}
      {reviews.length > 0 && (
        <details className="reviews-details">
          <summary>
            <h3>Detailed Reviews & Critiques ({reviews.length})</h3>
          </summary>
          <div className="reviews-list">
            {reviews.map((review) => (
              <div key={review.id} className="review-card">
                <div className="reviewer-info">
                  <strong>
                    {review.reviewer_provider}/{review.reviewer_model}
                  </strong>
                  <span className="confidence">
                    Confidence: {(review.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="review-details">
                  {review.reviews.map((r) => (
                    <div key={r.label} className="answer-review">
                      <div className="review-header">
                        <span className="label">Answer {r.label}</span>
                        <span className="overall-score">Overall: {r.scores.overall}/10</span>
                      </div>
                      <div className="scores">
                        <span>Correctness: {r.scores.correctness}</span>
                        <span>Completeness: {r.scores.completeness}</span>
                        <span>Clarity: {r.scores.clarity}</span>
                        <span>Helpfulness: {r.scores.helpfulness}</span>
                        <span>Safety: {r.scores.safety}</span>
                      </div>
                      <div className="critique">{r.critique}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* No results message */}
      {reviews.length === 0 && !aggregation && (
        <div className="no-results">
          <p>No evaluation results yet. Click "Run Evaluation" to have models vote on the answers.</p>
        </div>
      )}
    </div>
  );
}
