import { useState } from 'react';

interface Props {
  onSubmit: (question: string, blindReview: boolean) => void;
  disabled: boolean;
}

export function QuestionInput({ onSubmit, disabled }: Props) {
  const [question, setQuestion] = useState('');
  const [blindReview, setBlindReview] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim() && !disabled) {
      onSubmit(question.trim(), blindReview);
    }
  };

  return (
    <form className="question-input" onSubmit={handleSubmit}>
      <h3>Your Question</h3>
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Enter your question here..."
        rows={4}
        disabled={disabled}
      />
      <div className="options">
        <label className="blind-review-option">
          <input
            type="checkbox"
            checked={blindReview}
            onChange={(e) => setBlindReview(e.target.checked)}
            disabled={disabled}
          />
          <span>Blind review (hide model identities during evaluation)</span>
        </label>
      </div>
      <button type="submit" disabled={disabled || !question.trim()}>
        {disabled ? 'Running...' : 'Run'}
      </button>
    </form>
  );
}
