from typing import Tuple, List, Union, Dict

from collections import defaultdict

from overrides import overrides

from src.evaluate import (get_metrics as compute_em_and_f1,
                                      answer_json_to_strings)
from allennlp.training.metrics.metric import Metric


@Metric.register("EmAndF1Evaluator")
class EmAndF1Evaluator(Metric):
    """
    This :class:`Metric` takes the best span string computed by a model, along with the answer
    strings labeled in the data, and computes exact match and F1 score using the official DROP
    evaluator (which has special handling for numbers and for questions with multiple answer spans,
    among other things).
    """
    def __init__(self) -> None:
        self._total_em = 0.0
        self._total_f1 = 0.0
        self._total_p = 0.0
        self._total_r = 0.0
        self._count = 0
        self._answer_type_head_em = defaultdict(lambda: defaultdict(float))
        self._answer_type_head_f1 = defaultdict(lambda: defaultdict(float))
        self._answer_type_head_p = defaultdict(lambda: defaultdict(float))
        self._answer_type_head_r = defaultdict(lambda: defaultdict(float))
        self._answer_type_head_count = defaultdict(lambda: defaultdict(int))

    @overrides
    def __call__(self, prediction: Union[str, List], ground_truths: List):  # type: ignore
        """
        Parameters
        ----------
        prediction: ``Union[str, List]``
            The predicted answer from the model evaluated. This could be a string, or a list of string
            when multiple spans are predicted as answer.
        ground_truths: ``List``
            All the ground truth answer annotations.
        """
        self.call(prediction, ground_truths)

    def call(self, prediction: Union[str, List], ground_truths: List, predicted_ability: str) -> Union[str, List]:
        # If you wanted to split this out by answer type, you could look at [1] here and group by
        # that, instead of only keeping [0].
        ground_truth_answer_strings, ground_truth_answer_types = list(zip(*[answer_json_to_strings(annotation) for annotation in ground_truths]))
        (exact_match, f1_score, p_score, r_score), maximizing_ground_truth_index = EmAndF1Evaluator.metric_max_over_ground_truths(
                compute_em_and_f1,
                prediction,
                ground_truth_answer_strings
        )
        self._total_em += exact_match
        self._total_f1 += f1_score
        self._total_p += p_score
        self._total_r += r_score
        self._count += 1

        # Best answer type is selected, just as in drop_eval
        answer_type = ground_truth_answer_types[maximizing_ground_truth_index]
        self._answer_type_head_em[answer_type][predicted_ability] += exact_match
        self._answer_type_head_f1[answer_type][predicted_ability] += f1_score
        self._answer_type_head_p[answer_type][predicted_ability] += p_score
        self._answer_type_head_r[answer_type][predicted_ability] += r_score
        self._answer_type_head_count[answer_type][predicted_ability] += 1

        return (exact_match, f1_score, p_score, r_score), ground_truths[maximizing_ground_truth_index]

    @overrides
    def get_metric(self, reset: bool = False) -> Tuple[Tuple[float, float], Dict[str, float]]:
        """
        Returns
        -------
        Average exact match and F1 score (in that order) as computed by the official DROP script
        over all inputs.
        """
        exact_match = self._total_em / self._count if self._count > 0 else 0
        f1_score = self._total_f1 / self._count if self._count > 0 else 0
        p_score = self._total_p / self._count if self._count > 0 else 0
        r_score = self._total_r / self._count if self._count > 0 else 0
        
        scores_per_answer_type_and_head = defaultdict(lambda: {})
        scores_per_answer_type = {}
        scores_per_head = {}

        em_per_head = defaultdict(float)
        f1_per_head = defaultdict(float)
        p_per_head = defaultdict(float)
        r_per_head = defaultdict(float)
        count_per_head = defaultdict(int)

        for answer_type, head_count in self._answer_type_head_count.items():
            type_count = 0
            type_em = 0.0
            type_f1 = 0.0
            type_p = 0.0
            type_r = 0.0

            for head, count in head_count.items():
                type_count += count
                type_em += self._answer_type_head_em[answer_type][head]
                type_f1 += self._answer_type_head_f1[answer_type][head]
                type_p += self._answer_type_head_p[answer_type][head]
                type_r += self._answer_type_head_r[answer_type][head]

                em_per_head[head] += self._answer_type_head_em[answer_type][head]
                f1_per_head[head] += self._answer_type_head_f1[answer_type][head]
                p_per_head[head] += self._answer_type_head_p[answer_type][head]
                r_per_head[head] += self._answer_type_head_r[answer_type][head]
                count_per_head[head] += count

                type_head_exact_match = self._answer_type_head_em[answer_type][head] / count
                type_head_f1_score = self._answer_type_head_f1[answer_type][head] / count
                type_head_p_score = self._answer_type_head_p[answer_type][head] / count
                type_head_r_score = self._answer_type_head_r[answer_type][head] / count
                scores_per_answer_type_and_head[answer_type][head] = type_head_exact_match, type_head_f1_score, type_head_p_score, type_head_r_score, count
            
            scores_per_answer_type[answer_type] = type_em / type_count, type_f1 / type_count, type_p / type_count, type_r / type_count, type_count

        for head, count in count_per_head.items():
            scores_per_head[head] = em_per_head[head] / count, f1_per_head[head] / count, p_per_head[head] / count, r_per_head[head] / count, count
        
        if reset:
            self.reset()
        return (exact_match, f1_score, p_score, r_score), scores_per_answer_type_and_head, scores_per_answer_type, scores_per_head

    @overrides
    def reset(self):
        self._total_em = 0.0
        self._total_f1 = 0.0
        self._total_p = 0.0
        self._total_r = 0.0
        self._count = 0
        self._answer_type_head_em = defaultdict(lambda: defaultdict(float))
        self._answer_type_head_f1 = defaultdict(lambda: defaultdict(float))
        self._answer_type_head_p = defaultdict(lambda: defaultdict(float))
        self._answer_type_head_r = defaultdict(lambda: defaultdict(float))
        self._answer_type_head_count = defaultdict(lambda: defaultdict(int))
    
    def __str__(self):
        return f"EmAndF1Evaluator(em={self._total_em}, f1={self._total_f1}, p={self._total_p}, r={self._total_r}, _answer_type_head_em={self._answer_type_head_em}, _answer_type_head_count={self._answer_type_head_count})"


    @staticmethod
    def metric_max_over_ground_truths(metric_fn, prediction, ground_truths):
        """
        Modified from squad_eval.py in allennlp, changed to return maximizing index and match drop_eval
        
        Returns
        -------
        Maximum metric value and the matching index of ground truth
        """
        max_em_score = 0.0
        max_f1_score = 0.0
        max_p_score = 0.0
        max_r_score = 0.0
        maximizing_index = -1
        for i, ground_truth in enumerate(ground_truths):
            em_score, f1_score, p_score, r_score = metric_fn(prediction, ground_truth)
            if len(ground_truth) == 0 or (len(ground_truth) > 0 and ground_truth[0].strip() != ""):
                max_em_score = max(max_em_score, em_score)
                max_f1_score = max(max_f1_score, f1_score)
                max_p_score = max(max_p_score, p_score)
                max_r_score = max(max_r_score, r_score)
                if max_em_score == em_score and max_f1_score == f1_score and max_p_score == p_score and max_r_score == r_score:
                    maximizing_index = i

        return (max_em_score, max_f1_score, max_p_score, max_r_score), maximizing_index
