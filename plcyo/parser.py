from .errors import CompileError

DECLARATIONS = frozenset(
    ("title", "start", "speaker", "item", "int", "bool", "scene", "ending")
)
CHANGES = frozenset(("give", "take", "set", "increase", "decrease"))
OUTCOMES = frozenset(("death", "victory", "neutral"))


class Program:
    def __init__(self):
        self.titles = []
        self.starts = []
        self.speakers = []
        self.items = []
        self.variables = []
        self.scenes = []
        self.endings = []
        self.notes = []


class Speaker:
    def __init__(self, name, label, portrait):
        self.name = name
        self.label = label
        self.portrait = portrait


class Item:
    def __init__(self, name, label):
        self.name = name
        self.label = label


class Variable:
    def __init__(self, kind, name, value_token):
        self.kind = kind
        self.name = name
        self.value_token = value_token
        if kind == "bool":
            self.value = value_token.value == "true"
        else:
            self.value = value_token.value


class Scene:
    def __init__(self, name, background, body, choices):
        self.name = name
        self.background = background
        self.body = body
        self.choices = choices


class Ending:
    def __init__(self, name, outcome, text, missing_outcome_at):
        self.name = name
        self.outcome = outcome
        self.text = text
        self.missing_outcome_at = missing_outcome_at


class Narration:
    def __init__(self, text):
        self.text = text


class Dialogue:
    def __init__(self, speaker, text):
        self.speaker = speaker
        self.text = text


class Conditional:
    def __init__(self, test, then_steps, else_steps):
        self.test = test
        self.then_steps = then_steps
        self.else_steps = else_steps


class Change:
    def __init__(self, kind, name, value_token=None, by_token=None):
        self.kind = kind
        self.name = name
        self.value_token = value_token
        self.by_token = by_token


class Has:
    def __init__(self, name):
        self.name = name


class Lacks:
    def __init__(self, name):
        self.name = name


class Is:
    def __init__(self, name, value_token):
        self.name = name
        self.value_token = value_token
        self.value = value_token.value == "true"


class Compare:
    def __init__(self, name, op, number):
        self.name = name
        self.op = op
        self.number = number


class Choice:
    def __init__(self, text, when, changes, dest):
        self.text = text
        self.when = when
        self.changes = changes
        self.dest = dest


class To:
    def __init__(self, kind, name):
        self.kind = kind
        self.name = name


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.notes = []

    def peek(self):
        return self.tokens[self.pos]

    def at(self, kind):
        return self.peek().kind == kind

    def at_keyword(self, *words):
        tok = self.peek()
        return tok.kind == "keyword" and tok.value in words

    def advance(self):
        tok = self.tokens[self.pos]
        if tok.kind != "eof":
            self.pos += 1
        return tok

    def fail(self, token, message):
        raise CompileError(token.line, token.column, message)

    def note(self, token, message):
        self.notes.append(CompileError(token.line, token.column, message))

    def expect_keyword(self, word):
        tok = self.peek()
        if tok.kind == "keyword" and tok.value == word:
            return self.advance()
        if tok.kind == "eof" and word == "end":
            self.fail(tok, "missing end")
        self.fail(tok, f"expected '{word}'")

    def expect_name(self):
        tok = self.peek()
        if tok.kind == "keyword":
            self.fail(tok, f"'{tok.value}' is a keyword and cannot be a name")
        if tok.kind != "name":
            self.fail(tok, "expected a name")
        return self.advance()

    def expect_string(self):
        tok = self.peek()
        if tok.kind != "string":
            self.fail(tok, "expected a string")
        return self.advance()

    def expect_colon(self):
        tok = self.peek()
        if tok.kind != "colon":
            self.fail(tok, "expected ':'")
        return self.advance()

    def skip_misplaced_art(self):
        tok = self.peek()
        if not (tok.kind == "keyword" and tok.value in ("background", "portrait")):
            return False
        self.advance()
        self.expect_string()
        if tok.value == "background":
            self.note(tok, "background is only allowed on a scene")
        else:
            self.note(tok, "portrait is only allowed on a speaker")
        return True

    def parse_program(self):
        program = Program()
        while not self.at("eof"):
            if self.skip_misplaced_art():
                continue
            if self.at_keyword("title"):
                program.titles.append(self.parse_title())
            elif self.at_keyword("start"):
                program.starts.append(self.parse_start())
            elif self.at_keyword("speaker"):
                program.speakers.append(self.parse_speaker())
            elif self.at_keyword("item"):
                program.items.append(self.parse_item())
            elif self.at_keyword("int", "bool"):
                program.variables.append(self.parse_variable())
            elif self.at_keyword("scene"):
                program.scenes.append(self.parse_scene())
            elif self.at_keyword("ending"):
                program.endings.append(self.parse_ending())
            else:
                self.fail(
                    self.peek(),
                    "expected a title, start, speaker, item, variable, scene, or ending",
                )
        program.notes = self.notes
        return program

    def parse_title(self):
        keyword = self.advance()
        return keyword, self.expect_string()

    def parse_start(self):
        keyword = self.advance()
        return keyword, self.expect_name()

    def parse_speaker(self):
        self.advance()
        name = self.expect_name()
        label = self.expect_string()
        portrait = None
        while True:
            if self.at_keyword("portrait"):
                tok = self.advance()
                path = self.expect_string()
                if portrait is not None:
                    self.note(tok, "a speaker has one portrait")
                else:
                    portrait = path
                continue
            if self.at_keyword("background"):
                self.skip_misplaced_art()
                continue
            break
        return Speaker(name, label, portrait)

    def parse_item(self):
        self.advance()
        name = self.expect_name()
        label = self.expect_string()
        while self.skip_misplaced_art():
            pass
        return Item(name, label)

    def parse_variable(self):
        kind = self.advance()
        name = self.expect_name()
        if not self.at("equals"):
            self.fail(self.peek(), "expected '='")
        self.advance()
        if kind.value == "bool":
            if not self.at_keyword("true", "false"):
                self.fail(self.peek(), "expected true or false")
            value = self.advance()
        else:
            if not self.at("number"):
                self.fail(self.peek(), "expected a number")
            value = self.advance()
        return Variable(kind.value, name, value)

    def parse_scene(self):
        self.advance()
        name = self.expect_name()
        background = None
        while True:
            if self.at_keyword("background"):
                tok = self.advance()
                path = self.expect_string()
                if background is not None:
                    self.note(tok, "a scene has one background")
                else:
                    background = path
                continue
            if self.at_keyword("portrait"):
                self.skip_misplaced_art()
                continue
            break
        self.expect_colon()
        body, choices = self.parse_scene_contents()
        return Scene(name, background, body, choices)

    def parse_scene_contents(self):
        body = []
        while True:
            if self.at("eof"):
                self.fail(self.peek(), "missing end")
            if self.at_keyword("end"):
                self.advance()
                return body, []
            if self.at_keyword("choice"):
                break
            if self.at_keyword("else"):
                self.fail(self.peek(), "'else' without an 'if'")
            if self.skip_misplaced_art():
                continue
            if self.at_keyword(*DECLARATIONS):
                self.fail(self.peek(), "a declaration is not allowed inside a scene")
            body.append(self.parse_body_step())
        choices = []
        while self.at_keyword("choice"):
            choices.append(self.parse_choice())
        if self.at("eof"):
            self.fail(self.peek(), "missing end")
        if self.at_keyword("end"):
            self.advance()
            return body, choices
        if self.at("string") or self.at("name") or self.at_keyword("if", "else", *CHANGES):
            self.fail(self.peek(), "choices come after the scene body")
        self.fail(self.peek(), "missing end")

    def parse_body_step(self):
        if self.at_keyword(*CHANGES):
            return self.parse_change()
        return self.parse_line_or_if()

    def parse_line_or_if(self):
        if self.at("string"):
            return Narration(self.advance())
        if self.at_keyword("if"):
            return self.parse_if()
        if self.at("name"):
            name = self.advance()
            self.expect_colon()
            return Dialogue(name, self.expect_string())
        tok = self.peek()
        if tok.kind == "keyword":
            self.fail(tok, f"unexpected '{tok.value}'")
        self.fail(tok, "expected a line, a change, a conditional, or a choice")

    def parse_if(self):
        self.advance()
        test = self.parse_test()
        self.expect_colon()
        then_steps = self.parse_conditional_block()
        else_steps = None
        if self.at_keyword("else"):
            self.advance()
            if self.at_keyword("if"):
                self.fail(self.peek(), "else if is not allowed")
            self.expect_colon()
            else_steps = self.parse_conditional_block()
        if not self.at_keyword("end"):
            if self.at("eof"):
                self.fail(self.peek(), "missing end")
            self.fail(self.peek(), "expected 'end'")
        self.advance()
        return Conditional(test, then_steps, else_steps)

    def parse_conditional_block(self):
        steps = []
        while True:
            if self.at("eof"):
                self.fail(self.peek(), "missing end")
            if self.at_keyword("end", "else"):
                return steps
            if self.at_keyword("choice"):
                self.fail(self.peek(), "a choice is not allowed inside an if")
            if self.at_keyword(*CHANGES):
                self.fail(self.peek(), "a change is not allowed inside an if")
            if self.skip_misplaced_art():
                continue
            if self.at_keyword(*DECLARATIONS):
                self.fail(self.peek(), "a declaration is not allowed inside an if")
            steps.append(self.parse_line_or_if())

    def parse_choice(self):
        self.advance()
        text = self.expect_string()
        when = None
        if self.at_keyword("when"):
            self.advance()
            when = self.parse_test()
        self.expect_colon()
        changes = []
        dest = None
        while True:
            if self.at("eof"):
                self.fail(self.peek(), "missing end")
            if self.at_keyword("end"):
                end = self.advance()
                if dest is None:
                    self.fail(end, "choice has no to")
                return Choice(text, when, changes, dest)
            if self.skip_misplaced_art():
                continue
            if self.at_keyword(*CHANGES):
                if dest is not None:
                    self.fail(self.peek(), "to must be the last line of a choice")
                changes.append(self.parse_change())
                continue
            if self.at_keyword("to"):
                if dest is not None:
                    self.fail(self.peek(), "a choice has one destination")
                dest = self.parse_to()
                continue
            self.fail(self.peek(), "a choice holds changes and a destination, nothing else")

    def parse_to(self):
        self.advance()
        tok = self.peek()
        if not (tok.kind == "keyword" and tok.value in ("scene", "ending")):
            self.fail(tok, "expected 'scene' or 'ending'")
        kind = self.advance().value
        return To(kind, self.expect_name())

    def parse_change(self):
        kind = self.advance()
        name = self.expect_name()
        if kind.value in ("give", "take"):
            return Change(kind.value, name)
        if kind.value == "set":
            if self.at("equals"):
                self.fail(self.peek(), "set does not use '='")
            val = self.peek()
            if val.kind == "number" or (val.kind == "keyword" and val.value in ("true", "false")):
                self.advance()
                return Change("set", name, value_token=val)
            self.fail(val, "expected true, false, or a number")
        if not self.at_keyword("by"):
            self.fail(self.peek(), "expected 'by'")
        self.advance()
        if not self.at("number"):
            self.fail(self.peek(), "expected a number")
        num = self.advance()
        return Change(kind.value, name, by_token=num)

    def parse_test(self):
        tok = self.peek()
        if tok.kind == "arith":
            self.fail(tok, "arithmetic is not allowed in a test")
        if self.at_keyword("has", "lacks"):
            word = self.advance()
            if self.peek().kind == "arith":
                self.fail(self.peek(), "arithmetic is not allowed in a test")
            name = self.expect_name()
            node = Has(name) if word.value == "has" else Lacks(name)
            return self.finish_test(node)
        if tok.kind == "name":
            name = self.advance()
            if self.at_keyword("is"):
                self.advance()
                if not self.at_keyword("true", "false"):
                    self.fail(self.peek(), "expected true or false")
                value = self.advance()
                return self.finish_test(Is(name, value))
            if self.peek().kind == "arith":
                self.fail(self.peek(), "arithmetic is not allowed in a test")
            if self.at("op"):
                op = self.advance()
                nxt = self.peek()
                if nxt.kind == "arith":
                    self.fail(nxt, "arithmetic is not allowed in a test")
                if nxt.kind in ("name", "keyword"):
                    self.fail(nxt, "a test cannot mention two names")
                if nxt.kind != "number":
                    self.fail(nxt, "expected a number")
                number = self.advance()
                return self.finish_test(Compare(name, op, number))
            self.fail(self.peek(), "expected 'is' or a comparison")
        self.fail(tok, "expected a test")

    def finish_test(self, node):
        tok = self.peek()
        if tok.kind == "arith":
            self.fail(tok, "arithmetic is not allowed in a test")
        if tok.kind == "op":
            self.fail(tok, "a test is one question")
        if tok.kind == "name":
            self.fail(tok, "a test cannot mention two names")
        if tok.kind == "keyword" and tok.value in ("has", "lacks", "is", "true", "false"):
            self.fail(tok, "a test is one question")
        return node

    def parse_ending(self):
        self.advance()
        name = self.expect_name()
        outcome = None
        if self.at_keyword(*OUTCOMES):
            outcome = self.advance()
        while self.skip_misplaced_art():
            pass
        colon = self.expect_colon()
        text = None
        while not self.at_keyword("end"):
            if self.at("eof"):
                self.fail(self.peek(), "missing end")
            if self.skip_misplaced_art():
                continue
            if self.at("string"):
                if text is not None:
                    self.fail(self.peek(), "an ending holds exactly one line")
                text = self.advance()
                continue
            self.fail(self.peek(), "an ending holds exactly one line")
        end = self.advance()
        if text is None:
            self.fail(end, "an ending holds exactly one line")
        missing = None if outcome is not None else colon
        return Ending(name, outcome, text, missing)


def parse(tokens):
    return Parser(tokens).parse_program()