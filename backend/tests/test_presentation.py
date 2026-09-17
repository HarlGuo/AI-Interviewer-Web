import unittest

from app.presentation import clean_user_facing_text


class PresentationTests(unittest.TestCase):
    def test_removes_internal_resume_line_references(self) -> None:
        self.assertEqual(clean_user_facing_text("L030-L035：负责用户研究"), "负责用户研究")
        self.assertEqual(clean_user_facing_text("（L042） 项目经历需要核对"), "项目经历需要核对")

    def test_keeps_normal_user_facing_text(self) -> None:
        self.assertEqual(clean_user_facing_text("负责用户研究与需求分析"), "负责用户研究与需求分析")


if __name__ == "__main__":
    unittest.main()
