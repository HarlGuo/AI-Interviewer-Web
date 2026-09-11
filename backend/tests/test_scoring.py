import unittest

from app.schemas import DimensionScore
from app.scoring import DIMENSIONS, finalize_dimensions


def dimension(name: str, level: int | None = 3, evidence: list[str] | None = None) -> DimensionScore:
    return DimensionScore(name=name, level=level, basis="依据", evidence=evidence if evidence is not None else ["真实回答"], suggestion="建议")


class ScoringTests(unittest.TestCase):
    def test_equal_weighted_score_is_computed_by_backend(self) -> None:
        items = [dimension(name, index + 1 if index < 5 else None, [] if index == 5 else None) for index, name in enumerate(DIMENSIONS)]
        finalized, overall = finalize_dimensions(items, "真实回答")
        self.assertEqual(overall, 60)
        self.assertEqual([item.score for item in finalized[:5]], [20, 40, 60, 80, 100])
        self.assertIsNone(finalized[5].score)

    def test_downgrades_fabricated_evidence_to_insufficient(self) -> None:
        items = [dimension(name) for name in DIMENSIONS]
        items[0] = dimension(DIMENSIONS[0], evidence=["不存在的句子"])
        finalized, overall = finalize_dimensions(items, "真实回答")
        self.assertIsNone(finalized[0].score)
        self.assertEqual(finalized[0].evidence, [])
        self.assertIn("证据不足", finalized[0].basis)
        self.assertEqual(overall, 60)

    def test_requires_exact_dimension_set(self) -> None:
        with self.assertRaisesRegex(ValueError, "六个评分维度"):
            finalize_dimensions([dimension(DIMENSIONS[0])], "真实回答")
