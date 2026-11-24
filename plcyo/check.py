from .errors import CompileError
from .parser import Change, Compare, Conditional, Dialogue, Has, Is, Lacks


def check(program):
    errors = []
    if not program.titles:
        errors.append(CompileError(1, 1, "missing title"))
    elif len(program.titles) > 1:
        for keyword, _text in program.titles[1:]:
            errors.append(CompileError(keyword.line, keyword.column, "more than one title"))

    if not program.starts:
        errors.append(CompileError(1, 1, "missing start"))
    elif len(program.starts) > 1:
        for keyword, _name in program.starts[1:]:
            errors.append(CompileError(keyword.line, keyword.column, "more than one start"))

    speakers = {}
    for speaker in program.speakers:
        name = speaker.name.value
        if name in speakers:
            errors.append(CompileError(speaker.name.line, speaker.name.column, f"duplicate speaker '{name}'"))
        else:
            speakers[name] = speaker

    items = {}
    for item in program.items:
        name = item.name.value
        if name in items:
            errors.append(CompileError(item.name.line, item.name.column, f"duplicate item '{name}'"))
        else:
            items[name] = item

    variables = {}
    for variable in program.variables:
        name = variable.name.value
        if name in variables:
            errors.append(CompileError(variable.name.line, variable.name.column, f"duplicate variable '{name}'"))
        else:
            variables[name] = variable

    scenes = {}
    endings = {}
    places = []
    for scene in program.scenes:
        places.append(("scene", scene.name, scene))
    for ending in program.endings:
        places.append(("ending", ending.name, ending))
    places.sort(key=lambda item: (item[1].line, item[1].column))

    used = {}
    for kind, name_tok, node in places:
        name = name_tok.value
        if kind == "scene":
            scenes[name] = node
        else:
            endings[name] = node
        if name in used:
            if used[name] == kind:
                label = "scene" if kind == "scene" else "ending"
                errors.append(CompileError(name_tok.line, name_tok.column, f"duplicate {label} '{name}'"))
            else:
                errors.append(
                    CompileError(name_tok.line, name_tok.column, f"scene and ending share the name '{name}'")
                )
        else:
            used[name] = kind

    for scene in program.scenes:
        if not scene.choices:
            errors.append(
                CompileError(scene.name.line, scene.name.column, f"scene '{scene.name.value}' has no choices")
            )
        walk_steps(scene.body, speakers, items, variables, errors)
        for choice in scene.choices:
            if choice.when is not None:
                check_test(choice.when, items, variables, errors)
            for change in choice.changes:
                check_change(change, items, variables, errors)
            check_dest(choice.dest, scenes, endings, errors)

    for ending in program.endings:
        if ending.outcome is None:
            pos = ending.missing_outcome_at
            errors.append(
                CompileError(pos.line, pos.column, f"ending '{ending.name.value}' has no outcome")
            )

    for _keyword, name_tok in program.starts:
        if name_tok.value not in scenes:
            errors.append(CompileError(name_tok.line, name_tok.column, f"undeclared scene '{name_tok.value}'"))

    return errors


def walk_steps(steps, speakers, items, variables, errors):
    for step in steps:
        if isinstance(step, Dialogue):
            if step.speaker.value not in speakers:
                errors.append(
                    CompileError(step.speaker.line, step.speaker.column, f"undeclared speaker '{step.speaker.value}'")
                )
        elif isinstance(step, Change):
            check_change(step, items, variables, errors)
        elif isinstance(step, Conditional):
            check_test(step.test, items, variables, errors)
            walk_steps(step.then_steps, speakers, items, variables, errors)
            if step.else_steps is not None:
                walk_steps(step.else_steps, speakers, items, variables, errors)


def check_dest(dest, scenes, endings, errors):
    name = dest.name.value
    if dest.kind == "scene":
        if name not in scenes:
            errors.append(CompileError(dest.name.line, dest.name.column, f"undeclared scene '{name}'"))
    elif name not in endings:
        errors.append(CompileError(dest.name.line, dest.name.column, f"undeclared ending '{name}'"))


def check_test(test, items, variables, errors):
    if isinstance(test, (Has, Lacks)):
        if test.name.value not in items:
            errors.append(CompileError(test.name.line, test.name.column, f"undeclared item '{test.name.value}'"))
        return
    variable = variables.get(test.name.value)
    if variable is None:
        errors.append(CompileError(test.name.line, test.name.column, f"undeclared variable '{test.name.value}'"))
        return
    if isinstance(test, Is) and variable.kind != "bool":
        errors.append(
            CompileError(test.name.line, test.name.column, f"type mismatch: '{test.name.value}' is an int")
        )
    elif isinstance(test, Compare) and variable.kind != "int":
        errors.append(
            CompileError(test.name.line, test.name.column, f"type mismatch: '{test.name.value}' is a bool")
        )


def check_change(change, items, variables, errors):
    if change.kind in ("give", "take"):
        if change.name.value not in items:
            errors.append(CompileError(change.name.line, change.name.column, f"undeclared item '{change.name.value}'"))
        return
    variable = variables.get(change.name.value)
    if variable is None:
        errors.append(CompileError(change.name.line, change.name.column, f"undeclared variable '{change.name.value}'"))
    elif change.kind == "set":
        got_bool = change.value_token.kind == "keyword"
        if variable.kind == "bool" and not got_bool:
            errors.append(
                CompileError(
                    change.value_token.line,
                    change.value_token.column,
                    f"type mismatch: '{change.name.value}' is a bool",
                )
            )
        elif variable.kind == "int" and got_bool:
            errors.append(
                CompileError(
                    change.value_token.line,
                    change.value_token.column,
                    f"type mismatch: '{change.name.value}' is an int",
                )
            )
    elif variable.kind != "int":
        errors.append(
            CompileError(change.name.line, change.name.column, f"type mismatch: '{change.name.value}' is a bool")
        )
    if change.kind in ("increase", "decrease") and change.by_token is not None and change.by_token.value == 0:
        errors.append(
            CompileError(change.by_token.line, change.by_token.column, "type mismatch: by must be greater than zero")
        )