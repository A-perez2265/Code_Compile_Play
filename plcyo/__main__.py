import sys
from pathlib import Path

from .compile import compile_source
from .emit import dumps
from .errors import format_error

USAGE = """usage: plcyo check FILE
       plcyo build FILE [-o OUT]

check  Print errors and write nothing.
build  Write the story JSON when the file is clean.
       OUT defaults to FILE with a .json extension.
       Use -o - to write the JSON to stdout.
"""


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)
    if not args or args[0] in ("-h", "--help"):
        sys.stderr.write(USAGE)
        return 0 if args and args[0] in ("-h", "--help") else 2
    command = args[0]
    if command == "check":
        return cmd_check(args[1:])
    if command == "build":
        return cmd_build(args[1:])
    sys.stderr.write(USAGE)
    return 2


def cmd_check(args):
    if len(args) != 1 or args[0].startswith("-"):
        sys.stderr.write(USAGE)
        return 2
    text = read_source(args[0])
    if text is None:
        return 1
    _story, errors = compile_source(text)
    return report(args[0], errors)


def cmd_build(args):
    infile, outfile, status = parse_build_args(args)
    if status != 0:
        return status
    text = read_source(infile)
    if text is None:
        return 1
    story, errors = compile_source(text)
    if report(infile, errors) != 0:
        return 1
    data = dumps(story)
    if outfile is None:
        path = Path(infile)
        if path.suffix == ".plcyo":
            outfile = str(path.with_suffix(".json"))
        else:
            outfile = str(path.with_name(path.name + ".json"))
    if outfile == "-":
        sys.stdout.write(data)
        return 0
    try:
        with Path(outfile).open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(data)
    except OSError as err:
        sys.stderr.write(f"cannot write {outfile}: {err.strerror}\n")
        return 1
    return 0


def parse_build_args(args):
    infile = None
    outfile = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-o":
            if outfile is not None or i + 1 >= len(args):
                sys.stderr.write(USAGE)
                return None, None, 2
            outfile = args[i + 1]
            i += 2
            continue
        if arg.startswith("-"):
            sys.stderr.write(USAGE)
            return None, None, 2
        if infile is not None:
            sys.stderr.write(USAGE)
            return None, None, 2
        infile = arg
        i += 1
    if infile is None:
        sys.stderr.write(USAGE)
        return None, None, 2
    return infile, outfile, 0


def read_source(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        sys.stderr.write(f"{path}:1:1: error: file is not valid UTF-8\n")
        return None
    except OSError as err:
        detail = err.strerror or "cannot read file"
        sys.stderr.write(f"cannot read {path}: {detail}\n")
        return None


def report(filename, errors):
    if not errors:
        return 0
    for err in errors:
        sys.stderr.write(format_error(filename, err) + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())