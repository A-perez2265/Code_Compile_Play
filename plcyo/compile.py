from .check import check
from .emit import emit
from .errors import CompileError
from .lexer import lex
from .parser import parse


def compile_source(text):
    try:
        tokens = lex(text)
        program = parse(tokens)
    except CompileError as err:
        return None, [err]
    errors = list(program.notes) + check(program)
    errors.sort(key=lambda err: (err.line, err.column))
    if errors:
        return None, errors
    return emit(program), []