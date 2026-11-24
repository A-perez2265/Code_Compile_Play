from .errors import CompileError

KEYWORDS = frozenset(
    """
    title start speaker item int bool
    scene ending if else choice when
    give take set increase decrease to by
    has lacks is true false
    death victory neutral
    portrait background end
    """.split()
)


class Token:
    def __init__(self, kind, value, line, column):
        self.kind = kind
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r}, {self.line}, {self.column})"


def lex(source):
    tokens = []
    i = 0
    line = 1
    col = 1
    n = len(source)
    if source.startswith("\ufeff"):
        i = 1

    def bump():
        nonlocal i, line, col
        ch = source[i]
        i += 1
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1

    while i < n:
        ch = source[i]
        if ch in " \t":
            bump()
            continue
        if ch == "\n":
            bump()
            continue
        if ch == "\r":
            i += 1
            if i < n and source[i] == "\n":
                i += 1
            line += 1
            col = 1
            continue
        if ch == "#":
            while i < n and source[i] not in "\r\n":
                bump()
            continue
        if ch == '"':
            tokens.append(read_string(source, i, line, col))
            token = tokens[-1]
            i, line, col = token.end
            continue
        if ch == "-":
            raise CompileError(line, col, "a minus sign is not allowed")
        if ch in "+*/":
            tokens.append(Token("arith", ch, line, col))
            bump()
            continue
        if ch.isdigit():
            start_line, start_col = line, col
            start = i
            while i < n and source[i].isdigit():
                bump()
            tokens.append(Token("number", int(source[start:i]), start_line, start_col))
            continue
        if "a" <= ch <= "z":
            start_line, start_col = line, col
            start = i
            bump()
            while i < n and (("a" <= source[i] <= "z") or source[i].isdigit() or source[i] == "_"):
                bump()
            word = source[start:i]
            kind = "keyword" if word in KEYWORDS else "name"
            tokens.append(Token(kind, word, start_line, start_col))
            continue
        if ch == ":":
            tokens.append(Token("colon", ":", line, col))
            bump()
            continue
        if ch == "=":
            if i + 1 < n and source[i + 1] == "=":
                tokens.append(Token("op", "==", line, col))
                bump()
                bump()
            else:
                tokens.append(Token("equals", "=", line, col))
                bump()
            continue
        if ch == "!":
            if i + 1 < n and source[i + 1] == "=":
                tokens.append(Token("op", "!=", line, col))
                bump()
                bump()
            else:
                raise CompileError(line, col, "unexpected character '!'")
            continue
        if ch == "<":
            if i + 1 < n and source[i + 1] == "=":
                tokens.append(Token("op", "<=", line, col))
                bump()
                bump()
            else:
                tokens.append(Token("op", "<", line, col))
                bump()
            continue
        if ch == ">":
            if i + 1 < n and source[i + 1] == "=":
                tokens.append(Token("op", ">=", line, col))
                bump()
                bump()
            else:
                tokens.append(Token("op", ">", line, col))
                bump()
            continue
        label = f"'{ch}'" if ch.isprintable() else repr(ch)
        raise CompileError(line, col, f"unexpected character {label}")

    tokens.append(Token("eof", "", line, col))
    return tokens


def read_string(source, i, line, col):
    start_line, start_col = line, col
    i += 1
    col += 1
    chars = []
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in "\r\n":
            raise CompileError(start_line, start_col, "unclosed string")
        if ch == '"':
            i += 1
            col += 1
            token = Token("string", "".join(chars), start_line, start_col)
            token.end = (i, line, col)
            return token
        if ch == "\\":
            esc_col = col
            i += 1
            col += 1
            if i >= n or source[i] in "\r\n":
                raise CompileError(start_line, start_col, "unclosed string")
            esc = source[i]
            if esc == '"':
                chars.append('"')
            elif esc == "\\":
                chars.append("\\")
            else:
                raise CompileError(line, esc_col, "unknown escape in string")
            i += 1
            col += 1
            continue
        chars.append(ch)
        i += 1
        col += 1
    raise CompileError(start_line, start_col, "unclosed string")