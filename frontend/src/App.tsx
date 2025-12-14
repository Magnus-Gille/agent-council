import { useState } from 'react';
import type { Run, SelectedModel } from './types';
import { createRun, generateAnswers, evaluateRun, getRun } from './api';
import {
  ModelSelector,
  QuestionInput,
  AnswerCard,
  ReviewSection,
  RunHistory,
  ProgressIndicator,
} from './components';
import './App.css';

function App() {
  const [selectedModels, setSelectedModels] = useState<SelectedModel[]>([]);
  const [currentRun, setCurrentRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyRefresh, setHistoryRefresh] = useState(0);

  const pollRunUntilComplete = async (
    runId: number,
    maxAttempts = 20,
    delayMs = 1500
  ): Promise<Run> => {
    const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const run = await getRun(runId);
      if (run.status === 'complete' || run.status === 'failed' || run.aggregation) {
        return run;
      }
      await delay(delayMs);
    }
    return getRun(runId);
  };

  const handleSubmit = async (question: string, blindReview: boolean) => {
    if (selectedModels.length < 2) {
      setError('Please select at least 2 models');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Create run
      let run = await createRun({
        question,
        selected_models: selectedModels,
        blind_review: blindReview,
      });
      setCurrentRun(run);

      // Generate answers only - don't auto-evaluate
      run = await generateAnswers(run.id);

      // Fetch the complete run data to ensure answers are included
      const completeRun = await getRun(run.id);
      setCurrentRun(completeRun);

      setHistoryRefresh((n) => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleRunEvaluation = async () => {
    if (!currentRun) return;

    setEvaluating(true);
    setError(null);

    try {
      const runId = currentRun.id;
      const startedRun = await evaluateRun(runId);
      setCurrentRun(startedRun);

      const completedRun = await pollRunUntilComplete(runId);
      setCurrentRun(completedRun);
      setHistoryRefresh((n) => n + 1);

      if (completedRun.status === 'failed') {
        setError('Evaluation failed. Please try again.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Evaluation failed');
    } finally {
      setEvaluating(false);
    }
  };

  const handleSelectRun = async (runId: number) => {
    setLoading(true);
    try {
      const run = await getRun(runId);
      setCurrentRun(run);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load run');
    } finally {
      setLoading(false);
    }
  };

  const handleNewRun = () => {
    setCurrentRun(null);
    setError(null);
  };

  const canRunEvaluation =
    currentRun &&
    currentRun.answers &&
    currentRun.answers.filter(a => !a.error).length >= 2 &&
    !currentRun.aggregation &&
    !loading &&
    !evaluating;

  const sortedAnswers = () => {
    if (!currentRun?.answers || !currentRun.aggregation) {
      return currentRun?.answers || [];
    }
    const ranking = currentRun.aggregation.final_ranking;
    return [...currentRun.answers].sort(
      (a, b) => ranking.indexOf(a.label) - ranking.indexOf(b.label)
    );
  };

  return (
    <div className="app">
      <header>
        <h1>Agent Council</h1>
        <p>Multi-model AI evaluation and voting</p>
      </header>

      <div className="main-layout">
        <aside className="sidebar">
          <button className="new-run-btn" onClick={handleNewRun} disabled={loading || evaluating}>
            + New Run
          </button>
          <RunHistory
            onSelect={handleSelectRun}
            currentRunId={currentRun?.id}
            refreshTrigger={historyRefresh}
          />
        </aside>

        <main className="content">
          {!currentRun && (
            <div className="setup-section">
              <ModelSelector
                selectedModels={selectedModels}
                onChange={setSelectedModels}
              />
              <QuestionInput onSubmit={handleSubmit} disabled={loading} />
            </div>
          )}

          {error && <div className="error-banner">{error}</div>}

          {(loading || evaluating) && (
            <ProgressIndicator
              phase={evaluating ? 'evaluating' : 'generating'}
              models={currentRun?.selected_models?.map(m => `${m.provider}/${m.model_name}`) || selectedModels.map(m => `${m.provider}/${m.model_name}`)}
            />
          )}

          {currentRun && currentRun.answers && currentRun.answers.length > 0 && (
            <div className="results-section">
              <div className="question-display">
                <h3>Question</h3>
                <p>{currentRun.question}</p>
              </div>

              <div className="answers-section">
                <h3>Answers {currentRun.aggregation && '(Ranked)'}</h3>
                <div className="answers-grid">
                  {sortedAnswers().map((answer, index) => (
                    <AnswerCard
                      key={answer.id}
                      answer={answer}
                      showProvider={currentRun.status === 'complete'}
                      rank={currentRun.aggregation ? index : undefined}
                      isWinner={currentRun.aggregation?.final_ranking[0] === answer.label}
                    />
                  ))}
                </div>
              </div>

              {canRunEvaluation && (
                <div className="evaluation-action">
                  <button
                    className="evaluate-btn"
                    onClick={handleRunEvaluation}
                    disabled={evaluating}
                  >
                    Run Evaluation - Have Models Vote on Best Answer
                  </button>
                  <p className="evaluate-hint">
                    Each model will review and score the other answers, then vote on the best one.
                  </p>
                </div>
              )}

              {currentRun.reviews && currentRun.reviews.length > 0 && (
                <ReviewSection
                  reviews={currentRun.reviews}
                  aggregation={currentRun.aggregation}
                  answers={currentRun.answers}
                />
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
