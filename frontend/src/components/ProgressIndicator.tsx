import { useState, useEffect } from 'react';

interface Props {
  phase: 'generating' | 'evaluating';
  models: string[];
}

const THINKING_WORDS = [
  'Pondering',
  'Contemplating',
  'Analyzing',
  'Considering',
  'Reasoning',
  'Deliberating',
  'Examining',
  'Weighing options',
  'Reflecting',
  'Processing',
  'Formulating',
  'Synthesizing',
  'Noodling',
  'Cogitating',
  'Ruminating',
  'Mulling it over',
  'Thinking deeply',
  'Working through it',
];

const EVALUATION_WORDS = [
  'Judging',
  'Comparing',
  'Scoring',
  'Ranking',
  'Assessing',
  'Critiquing',
  'Evaluating',
  'Reviewing',
  'Deliberating',
  'Weighing merits',
  'Forming opinions',
  'Rating responses',
  'Analyzing quality',
  'Checking facts',
  'Measuring clarity',
];

export function ProgressIndicator({ phase, models }: Props) {
  const [wordIndex, setWordIndex] = useState(0);
  const [dots, setDots] = useState('');

  const words = phase === 'generating' ? THINKING_WORDS : EVALUATION_WORDS;

  useEffect(() => {
    const wordInterval = setInterval(() => {
      setWordIndex((i) => (i + 1) % words.length);
    }, 2000);

    const dotInterval = setInterval(() => {
      setDots((d) => (d.length >= 3 ? '' : d + '.'));
    }, 400);

    return () => {
      clearInterval(wordInterval);
      clearInterval(dotInterval);
    };
  }, [words.length]);

  const currentWord = words[wordIndex];

  return (
    <div className="progress-indicator">
      <div className="progress-spinner"></div>
      <div className="progress-content">
        <div className="progress-phase">
          {phase === 'generating' ? (
            <>
              <span className="phase-icon">💭</span>
              <span className="phase-title">Generating Answers</span>
            </>
          ) : (
            <>
              <span className="phase-icon">⚖️</span>
              <span className="phase-title">Models Voting</span>
            </>
          )}
        </div>

        <div className="progress-models">
          {models.map((model, i) => (
            <div key={i} className="model-status">
              <span className="model-dot"></span>
              <span className="model-name">{model}</span>
            </div>
          ))}
        </div>

        <div className="progress-thinking">
          <span className="thinking-word">{currentWord}</span>
          <span className="thinking-dots">{dots}</span>
        </div>
      </div>
    </div>
  );
}
