class CompileError(Exception):
    def __init__(self, line, column, message):
        super().__init__(message)
        self.line = line
        self.column = column
        self.message = message

    def __str__(self):
        return f"{self.line}:{self.column}: error: {self.message}"


def format_error(filename, err):
    return f"{filename}:{err.line}:{err.column}: error: {err.message}"