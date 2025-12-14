export interface ModelParams {
  temperature: number;
  max_tokens: number;
  system_prompt?: string;
  instance_label?: string;
}

export interface SelectedModel {
  id?: number;
  run_id?: number;
  provider: string;
  model_name: string;
  params: ModelParams;
}

export interface ModelInfo {
  provider: string;
  model_id: string;
  display_name: string;
}

export interface ProviderInfo {
  name: string;
  available: boolean;
}

export interface ReviewScores {
  correctness: number;
  completeness: number;
  clarity: number;
  helpfulness: number;
  safety: number;
  overall: number;
}

export interface AnswerReview {
  label: string;
  scores: ReviewScores;
  critique: string;
}

export interface Answer {
  id: number;
  run_id: number;
  producer_model: string;
  provider: string;
  label: string;
  text: string;
  latency_ms: number;
  tokens_in?: number;
  tokens_out?: number;
  error?: string;
}

export interface Review {
  id: number;
  run_id: number;
  reviewer_model: string;
  reviewer_provider: string;
  reviews: AnswerReview[];
  rank_order: string[];
  confidence: number;
  raw_response?: string;
}

export interface VoteBreakdown {
  borda_totals: Record<string, number>;
  first_place_votes: Record<string, number>;
  score_averages: Record<string, number>;
}

export interface AggregationResult {
  id: number;
  run_id: number;
  final_ranking: string[];
  vote_breakdown: VoteBreakdown;
  method_version: string;
}

export type RunStatus =
  | 'pending'
  | 'generating_answers'
  | 'answers_complete'
  | 'evaluating'
  | 'complete'
  | 'failed';

export interface Run {
  id: number;
  created_at: string;
  question: string;
  status: RunStatus;
  blind_review: boolean;
  selected_models?: SelectedModel[];
  answers?: Answer[];
  reviews?: Review[];
  aggregation?: AggregationResult;
}

export interface RunCreate {
  question: string;
  selected_models: SelectedModel[];
  blind_review: boolean;
}
