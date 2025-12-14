from dataclasses import dataclass


@dataclass
class VoteBreakdown:
    borda_totals: dict[str, int]
    first_place_votes: dict[str, int]
    score_averages: dict[str, float]


@dataclass
class AggregationOutput:
    final_ranking: list[str]
    vote_breakdown: VoteBreakdown


class VotingService:
    def __init__(self):
        pass

    def aggregate_votes(
        self,
        reviews: list[dict],
        label_to_model: dict[str, str],
    ) -> AggregationOutput:
        """
        Aggregate reviewer votes using Borda count.

        Args:
            reviews: List of review dicts with 'reviewer_model', 'reviewer_provider',
                     'rank_order', and 'reviews' keys
            label_to_model: Mapping from answer label to model identifier
        """
        all_labels = set(label_to_model.keys())
        borda_totals: dict[str, int] = {label: 0 for label in all_labels}
        first_place_votes: dict[str, int] = {label: 0 for label in all_labels}
        score_sums: dict[str, float] = {label: 0.0 for label in all_labels}
        score_counts: dict[str, int] = {label: 0 for label in all_labels}
        correctness_sums: dict[str, float] = {label: 0.0 for label in all_labels}

        for review in reviews:
            rank_order = review.get("rank_order", [])
            if not rank_order:
                continue

            # Count all votes including self-votes (blind review means models
            # don't know which answer is theirs)
            n = len(rank_order)

            # Borda points: top gets n-1, next gets n-2, etc.
            for position, label in enumerate(rank_order):
                if label in borda_totals:
                    borda_totals[label] += (n - 1 - position)

            # First place votes
            if rank_order and rank_order[0] in first_place_votes:
                first_place_votes[rank_order[0]] += 1

            # Collect scores for averaging (include all scores)
            for answer_review in review.get("reviews", []):
                label = answer_review.get("label")
                if label and label in score_sums:
                    scores = answer_review.get("scores", {})
                    overall = scores.get("overall", 0)
                    correctness = scores.get("correctness", 0)
                    score_sums[label] += overall
                    correctness_sums[label] += correctness
                    score_counts[label] += 1

        # Compute averages
        score_averages = {}
        correctness_averages = {}
        for label in all_labels:
            if score_counts[label] > 0:
                score_averages[label] = score_sums[label] / score_counts[label]
                correctness_averages[label] = correctness_sums[label] / score_counts[label]
            else:
                score_averages[label] = 0.0
                correctness_averages[label] = 0.0

        # Sort by Borda, then by average overall score, then by correctness
        sorted_labels = sorted(
            all_labels,
            key=lambda l: (
                borda_totals[l],
                score_averages[l],
                correctness_averages[l],
            ),
            reverse=True,
        )

        return AggregationOutput(
            final_ranking=sorted_labels,
            vote_breakdown=VoteBreakdown(
                borda_totals=borda_totals,
                first_place_votes=first_place_votes,
                score_averages=score_averages,
            ),
        )
