import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from plcyo import compile_source
from plcyo.lexer import lex

HERE = Path(__file__).resolve().parent
COMPILER = HERE.parent
GATE_SOURCE = COMPILER / "samples" / "the-gate.plcyo"
GATE_JSON = COMPILER / "the-gate.json"


def pairs(errors):
    return [(err.line, err.column, err.message) for err in errors]


def column_of(src, line, snippet):
    return src.splitlines()[line - 1].index(snippet) + 1


def wrap(inner, decls=""):
    return (
        'title "T"\n'
        "start room\n"
        f"{decls}"
        "scene room:\n"
        f"{inner}"
        "end\n"
        "ending out neutral:\n"
        '"Done."\n'
        "end\n"
    )


def same_order(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        if list(left) != list(right):
            return False
        return all(same_order(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same_order(a, b) for a, b in zip(left, right))
    return left == right


class GateTests(unittest.TestCase):
    def test_gate_matches_expected_json(self):
        story, errors = compile_source(GATE_SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(errors, [])
        expected = json.loads(GATE_JSON.read_text(encoding="utf-8"))
        self.assertTrue(same_order(story, expected))

    def test_cli_check_is_silent_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "the-gate.plcyo"
            source.write_text(GATE_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
            proc = run(["check", str(source)], cwd=folder)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(proc.stderr, "")
            self.assertEqual(list(folder.iterdir()), [source])

    def test_cli_build_matches_gate_json(self):
        proc = run(["build", str(GATE_SOURCE), "-o", "-"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        got = json.loads(proc.stdout)
        expected = json.loads(GATE_JSON.read_text(encoding="utf-8"))
        self.assertTrue(same_order(got, expected))

    def test_failed_build_writes_nothing_and_keeps_old_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "bad.plcyo"
            source.write_text('title "T"\n', encoding="utf-8")
            output = folder / "bad.json"
            output.write_text("KEEP\n", encoding="utf-8")
            proc = run(["build", str(source), "-o", str(output)])
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "KEEP\n")
            self.assertIn("missing start", proc.stderr)
            self.assertEqual(proc.stdout, "")


class StoryTests(unittest.TestCase):
    def test_minimal_story(self):
        story, errors = compile_source(wrap('choice "c":\nto ending out\nend\n'))
        self.assertEqual(errors, [])
        self.assertEqual(story["title"], "T")
        self.assertEqual(story["start"], "room")
        self.assertEqual(story["speakers"], [])
        self.assertEqual(story["items"], [])
        self.assertEqual(story["variables"], [])
        self.assertEqual(story["scenes"][0]["id"], "room")
        self.assertNotIn("background", story["scenes"][0])
        self.assertEqual(story["scenes"][0]["body"], [])
        self.assertEqual(story["scenes"][0]["choices"][0]["to"], {"ending": "out"})
        self.assertNotIn("when", story["scenes"][0]["choices"][0])
        self.assertNotIn("changes", story["scenes"][0]["choices"][0])
        self.assertEqual(
            story["endings"],
            [{"id": "out", "outcome": "neutral", "text": "Done."}],
        )

    def test_feature_story_keeps_source_order(self):
        src = """
int courage = 2
bool marked = true
item key "Iron key"
item lamp "Lamp"
speaker reaper "The Reaper" portrait "art/reaper.png"
speaker echo "Echo"
title "Ash Stair"
start hall

scene hall background "art/hall.png":
"The stair is cold."
reaper: "Down."
set courage 1
if marked is true:
"Marked."
if courage >= 1:
echo: "You can hear it."
end
else:
"Unmarked."
end
if lacks lamp:
"No lamp."
end
give lamp
choice "Take the key" when lacks key:
give key
set marked true
increase courage by 2
to scene door
end
choice "Leave" when courage > 0:
decrease courage by 1
take lamp
to ending fell
end
end

scene door:
"A door."
choice "Back" when has key:
to scene hall
end
choice "Through":
to ending fell
end
end

ending fell death:
"The dark keeps you."
end
"""
        story, errors = compile_source(src)
        self.assertEqual(errors, [])
        self.assertEqual(list(story), ["title", "start", "speakers", "items", "variables", "scenes", "endings"])
        self.assertEqual([item["id"] for item in story["speakers"]], ["reaper", "echo"])
        self.assertNotIn("portrait", story["speakers"][1])
        self.assertEqual(story["speakers"][0]["portrait"], "art/reaper.png")
        self.assertEqual([item["id"] for item in story["items"]], ["key", "lamp"])
        self.assertEqual(story["variables"][0], {"id": "courage", "type": "int", "value": 2})
        self.assertEqual(story["variables"][1], {"id": "marked", "type": "bool", "value": True})
        hall = story["scenes"][0]
        self.assertEqual(
            hall["body"][3],
            {
                "if": {"is": "marked", "value": True},
                "then": [
                    {"text": "Marked."},
                    {
                        "if": {"compare": "courage", "op": ">=", "value": 1},
                        "then": [{"speaker": "echo", "text": "You can hear it."}],
                    },
                ],
                "else": [{"text": "Unmarked."}],
            },
        )
        self.assertNotIn("else", hall["body"][4])
        self.assertEqual(hall["body"][4]["if"], {"lacks": "lamp"})
        self.assertEqual(hall["body"][5], {"give": "lamp"})
        take = hall["choices"][0]
        self.assertEqual(take["when"], {"lacks": "key"})
        self.assertEqual(
            take["changes"],
            [
                {"give": "key"},
                {"set": "marked", "value": True},
                {"increase": "courage", "by": 2},
            ],
        )
        self.assertEqual(take["to"], {"scene": "door"})
        leave = hall["choices"][1]
        self.assertEqual(leave["changes"][0], {"decrease": "courage", "by": 1})
        self.assertEqual(leave["changes"][1], {"take": "lamp"})
        self.assertEqual(leave["to"], {"ending": "fell"})
        door = story["scenes"][1]
        self.assertEqual(list(door), ["id", "body", "choices"])
        self.assertNotIn("changes", door["choices"][0])
        self.assertEqual(door["choices"][1]["to"], {"ending": "fell"})
        self.assertEqual(story["endings"][0]["outcome"], "death")

    def test_empty_else_is_kept_and_omitted_else_is_absent(self):
        kept, errors = compile_source(
            wrap(
                'if marked is true:\n"yes"\nelse:\nend\nchoice "c":\nto ending out\nend\n',
                decls="bool marked = false\n",
            )
        )
        self.assertEqual(errors, [])
        self.assertEqual(kept["scenes"][0]["body"][0]["else"], [])
        omitted, errors = compile_source(
            wrap(
                'if marked is true:\n"yes"\nend\nchoice "c":\nto ending out\nend\n',
                decls="bool marked = false\n",
            )
        )
        self.assertEqual(errors, [])
        self.assertNotIn("else", omitted["scenes"][0]["body"][0])

    def test_comparisons_and_forward_declarations(self):
        src = """
scene room:
choice "eq" when courage == 0:
to ending out
end
choice "ne" when courage != 1:
to ending out
end
choice "lt" when courage < 2:
to ending out
end
choice "le" when courage <= 2:
to ending out
end
choice "gt" when courage > 0:
decrease courage by 100
to ending out
end
choice "ge" when courage >= 0:
to ending out
end
end
ending out victory:
"z"
end
title "Late"
start room
int courage = 0
"""
        story, errors = compile_source(src)
        self.assertEqual(errors, [])
        ops = [choice["when"]["op"] for choice in story["scenes"][0]["choices"]]
        self.assertEqual(ops, ["==", "!=", "<", "<=", ">", ">="])
        self.assertEqual(story["scenes"][0]["choices"][4]["changes"], [{"decrease": "courage", "by": 100}])
        self.assertEqual(story["title"], "Late")
        self.assertEqual([variable["id"] for variable in story["variables"]], ["courage"])

    def test_strings_comments_and_escapes(self):
        src = """
# a comment with a " quote
title "say \\"hi\\" \\\\ path" # tail
start room
scene room:
"a # b"
choice "c":
to ending out
end
end
ending out death:
"line"
end
"""
        story, errors = compile_source(src)
        self.assertEqual(errors, [])
        self.assertEqual(story["title"], 'say "hi" \\ path')
        self.assertEqual(story["scenes"][0]["body"][0]["text"], "a # b")

    def test_same_spelling_in_separate_namespaces(self):
        src = """
title "T"
start gate
speaker gate "Gate"
item gate "Gate item"
bool gate = false
scene gate:
choice "c" when gate is false:
give gate
set gate true
to ending out
end
end
ending out neutral:
"z"
end
"""
        story, errors = compile_source(src)
        self.assertEqual(errors, [])
        self.assertEqual(story["scenes"][0]["choices"][0]["when"], {"is": "gate", "value": False})


class ErrorTests(unittest.TestCase):
    def assert_has(self, src, line, snippet, message):
        story, errors = compile_source(src)
        self.assertIsNone(story)
        found = (line, column_of(src, line, snippet), message)
        self.assertIn(found, pairs(errors), pairs(errors))
        return errors

    def test_error_shape_from_the_cli(self):
        src = wrap('choice "c":\ngive key\nto ending out\nend\n')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "the-gate.plcyo"
            path.write_text(src, encoding="utf-8")
            proc = run(["check", "the-gate.plcyo"], cwd=tmp)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        line = src.splitlines().index("give key") + 1
        column = column_of(src, line, "key")
        self.assertEqual(
            proc.stderr,
            f"the-gate.plcyo:{line}:{column}: error: undeclared item 'key'\n",
        )

    def test_tab_counts_as_one_column(self):
        src = 'title "T"\nstart room\nscene room:\nchoice "c":\n\tgive nope\nto ending out\nend\nend\nending out neutral:\n"z"\nend\n'
        line = src.splitlines().index("\tgive nope") + 1
        self.assertEqual(column_of(src, line, "nope"), 7)
        self.assert_has(src, line, "nope", "undeclared item 'nope'")

    def test_missing_title_and_start(self):
        errors = self.assert_has('scene room:\nchoice "c":\nto ending out\nend\nend\n', 1, "scene", "missing title")
        self.assertIn((1, 1, "missing start"), pairs(errors))

    def test_more_than_one_title_and_start(self):
        src = (
            'title "A"\n'
            'title "B"\n'
            "start room\n"
            "start other\n"
            "scene room:\n"
            'choice "c":\n'
            "to ending out\n"
            "end\n"
            "end\n"
            "ending out neutral:\n"
            '"z"\n'
            "end\n"
        )
        self.assert_has(src, 2, "title", "more than one title")
        self.assert_has(src, 4, "start", "more than one start")

    def test_duplicates_and_shared_place_names(self):
        self.assert_has(
            wrap('choice "c":\nto ending out\nend\n', decls='speaker cat "Cat"\nspeaker cat "Other"\n'),
            4,
            "cat",
            "duplicate speaker 'cat'",
        )
        src = (
            'title "T"\n'
            "start room\n"
            'item key "Key"\n'
            'item key "Other"\n'
            "int courage = 0\n"
            "bool courage = true\n"
            "scene room:\n"
            'choice "c":\n'
            "to ending out\n"
            "end\n"
            "end\n"
            "scene room:\n"
            'choice "d":\n'
            "to ending out\n"
            "end\n"
            "end\n"
            "ending out neutral:\n"
            '"z"\n'
            "end\n"
            "ending out death:\n"
            '"again"\n'
            "end\n"
        )
        self.assert_has(src, 4, "key", "duplicate item 'key'")
        self.assert_has(src, 6, "courage", "duplicate variable 'courage'")
        self.assert_has(src, 12, "room", "duplicate scene 'room'")
        self.assert_has(src, 20, "out", "duplicate ending 'out'")
        shared = (
            'title "T"\n'
            "start room\n"
            "scene room:\n"
            'choice "c":\n'
            "to ending room\n"
            "end\n"
            "end\n"
            "ending room victory:\n"
            '"z"\n'
            "end\n"
        )
        self.assert_has(shared, 8, "room", "scene and ending share the name 'room'")

    def test_undeclared_names_and_destinations(self):
        self.assert_has(
            wrap('ghost: "boo"\nchoice "c":\nto ending out\nend\n'),
            4,
            "ghost",
            "undeclared speaker 'ghost'",
        )
        self.assert_has(
            wrap('choice "c" when has key:\nto ending out\nend\n'),
            4,
            "key",
            "undeclared item 'key'",
        )
        self.assert_has(
            wrap("set marked true\n" 'choice "c":\n' "to ending out\nend\n"),
            4,
            "marked",
            "undeclared variable 'marked'",
        )
        self.assert_has(
            'title "T"\nstart missing\nscene room:\nchoice "c":\nto ending out\nend\nend\nending out neutral:\n"z"\nend\n',
            2,
            "missing",
            "undeclared scene 'missing'",
        )
        self.assert_has(
            'title "T"\nstart out\nscene room:\nchoice "c":\nto ending out\nend\nend\nending out neutral:\n"z"\nend\n',
            2,
            "out",
            "undeclared scene 'out'",
        )
        self.assert_has(
            wrap('choice "c":\nto scene out\nend\n'),
            5,
            "out",
            "undeclared scene 'out'",
        )
        self.assert_has(
            wrap('choice "c":\nto ending room\nend\n'),
            5,
            "room",
            "undeclared ending 'room'",
        )

    def test_type_mismatch(self):
        decls = "bool marked = false\nint courage = 0\n"
        self.assert_has(
            wrap("set marked 1\n" 'choice "c":\n' "to ending out\nend\n", decls=decls),
            6,
            "1",
            "type mismatch: 'marked' is a bool",
        )
        self.assert_has(
            wrap("set courage true\n" 'choice "c":\n' "to ending out\nend\n", decls=decls),
            6,
            "true",
            "type mismatch: 'courage' is an int",
        )
        self.assert_has(
            wrap("increase marked by 1\n" 'choice "c":\n' "to ending out\nend\n", decls=decls),
            6,
            "marked",
            "type mismatch: 'marked' is a bool",
        )
        self.assert_has(
            wrap("decrease courage by 0\n" 'choice "c":\n' "to ending out\nend\n", decls=decls),
            6,
            "0",
            "type mismatch: by must be greater than zero",
        )
        self.assert_has(
            wrap('if courage is true:\n"x"\nend\nchoice "c":\nto ending out\nend\n', decls=decls),
            6,
            "courage",
            "type mismatch: 'courage' is an int",
        )
        self.assert_has(
            wrap('if marked >= 1:\n"x"\nend\nchoice "c":\nto ending out\nend\n', decls=decls),
            6,
            "marked",
            "type mismatch: 'marked' is a bool",
        )

    def test_scene_and_ending_shape(self):
        self.assert_has(wrap('"hi"\n'), 3, "room", "scene 'room' has no choices")
        src = 'title "T"\nstart room\nscene room:\nchoice "c":\nto ending out\nend\nend\nending out:\n"z"\nend\n'
        self.assert_has(src, 8, ":", "ending 'out' has no outcome")

    def test_art_in_the_wrong_place(self):
        self.assert_has(
            wrap('choice "c":\nto ending out\nend\n').replace(
                "scene room:\n", 'scene room portrait "art/x.png":\n'
            ),
            3,
            "portrait",
            "portrait is only allowed on a speaker",
        )
        self.assert_has(
            wrap(
                'choice "c":\nto ending out\nend\n',
                decls='speaker reaper "The Reaper" background "art/x.png"\n',
            ),
            3,
            "background",
            "background is only allowed on a scene",
        )
        self.assert_has(
            wrap('background "art/x.png"\nchoice "c":\nto ending out\nend\n'),
            4,
            "background",
            "background is only allowed on a scene",
        )
        self.assert_has(
            'title "T"\nstart room\nscene room:\nchoice "c":\nto ending out\nend\nend\nending out victory background "art/x.png":\n"z"\nend\n',
            8,
            "background",
            "background is only allowed on a scene",
        )

    def test_syntax_errors(self):
        self.assert_has('title "oops\n', 1, '"', "unclosed string")
        self.assert_has("int courage = -1\n", 1, "-", "a minus sign is not allowed")
        self.assert_has('item if "no"\n', 1, "if", "'if' is a keyword and cannot be a name")
        self.assert_has(
            wrap('if marked is true:\n"yes"\nelse if marked is false:\n"no"\nend\nchoice "c":\nto ending out\nend\n', "bool marked = false\n"),
            7,
            "if",
            "else if is not allowed",
        )
        self.assert_has(
            wrap('if marked is true:\ngive key\nend\nchoice "c":\nto ending out\nend\n', "bool marked = false\nitem key \"Key\"\n"),
            7,
            "give",
            "a change is not allowed inside an if",
        )
        self.assert_has(
            wrap('if marked is true:\nchoice "inner":\nto ending out\nend\nend\nchoice "c":\nto ending out\nend\n', "bool marked = false\n"),
            6,
            "choice",
            "a choice is not allowed inside an if",
        )
        self.assert_has(
            wrap('if courage >= 1 + 2:\n"x"\nend\nchoice "c":\nto ending out\nend\n', "int courage = 0\n"),
            5,
            "+",
            "arithmetic is not allowed in a test",
        )
        self.assert_has(
            wrap('if courage + 1 >= 2:\n"x"\nend\nchoice "c":\nto ending out\nend\n', "int courage = 0\n"),
            5,
            "+",
            "arithmetic is not allowed in a test",
        )
        self.assert_has(
            wrap('choice "c":\ngive key\nend\n', 'item key "Key"\n'),
            7,
            "end",
            "choice has no to",
        )
        self.assert_has(
            wrap('choice "c":\nto ending out\ngive key\nend\n', 'item key "Key"\n'),
            7,
            "give",
            "to must be the last line of a choice",
        )
        self.assert_has(
            wrap('choice "c":\nto room\nend\n'),
            5,
            "room",
            "expected 'scene' or 'ending'",
        )
        src = 'title "T"\nstart room\nscene room:\nchoice "c":\nto ending out\nend\n'
        story, errors = compile_source(src)
        self.assertIsNone(story)
        self.assertEqual(errors[0].message, "missing end")
        self.assertEqual(errors[0].line, src.count("\n") + 1)
        self.assertEqual(errors[0].column, 1)
        self.assert_has(
            wrap("set marked = true\n" 'choice "c":\n' "to ending out\nend\n", "bool marked = true\n"),
            5,
            "=",
            "set does not use '='",
        )
        self.assert_has('title "\\q"\n', 1, "\\", "unknown escape in string")
        self.assert_has(
            wrap('if courage >= marked:\n"x"\nend\nchoice "c":\nto ending out\nend\n', "int courage = 0\nbool marked = false\n"),
            6,
            "marked",
            "a test cannot mention two names",
        )


class LexerTests(unittest.TestCase):
    def test_gate_opening_tokens(self):
        tokens = lex('title "The Gate"\nstart gate\n')
        self.assertEqual(tokens[0].kind, "keyword")
        self.assertEqual((tokens[0].value, tokens[0].line, tokens[0].column), ("title", 1, 1))
        self.assertEqual(tokens[1].kind, "string")
        self.assertEqual((tokens[1].value, tokens[1].column), ("The Gate", 7))
        self.assertEqual((tokens[3].value, tokens[3].line, tokens[3].column), ("gate", 2, 7))
        self.assertEqual(tokens[-1].kind, "eof")


def run(args, cwd=COMPILER):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(COMPILER)
    return subprocess.run(
        [sys.executable, "-m", "plcyo", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


if __name__ == "__main__":
    unittest.main()