import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cobaye  # noqa: E402


class ParseTest(unittest.TestCase):
    def test_markdown_pairs(self):
        s = cobaye.from_markdown("```py\nprint(1)\n```\n\n```output\n1\n```\n```c\nx\n```\n", "t.md")
        self.assertEqual([(x["lang"], x["expected"], x["where"]) for x in s], [("python", "1\n", "t.md:1")])

    def test_norm_drops_ocaml_noise(self):
        self.assertEqual(cobaye.norm("OCaml version 4.14\n- : int =\n  3\n"), "- : int = 3")

    def test_unknown_language(self):
        with self.assertRaises(ValueError):
            cobaye.run([{"lang": "cobol", "code": "", "expected": ""}])


@unittest.skipUnless(shutil.which("docker"), "docker not installed")
class RunTest(unittest.TestCase):
    def test_example_course(self):
        bad = cobaye.run(cobaye.load(ROOT / "examples" / "course.md"))
        self.assertEqual([s["where"] for s, _ in bad], [f"{ROOT / 'examples' / 'course.md'}:36"])


if __name__ == "__main__":
    unittest.main()
