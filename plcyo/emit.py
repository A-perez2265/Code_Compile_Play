import json

from .parser import Change, Compare, Conditional, Dialogue, Has, Is, Lacks, Narration


def emit(program):
    story = {
        "title": program.titles[0][1].value,
        "start": program.starts[0][1].value,
        "speakers": [emit_speaker(speaker) for speaker in program.speakers],
        "items": [emit_item(item) for item in program.items],
        "variables": [emit_variable(variable) for variable in program.variables],
        "scenes": [emit_scene(scene) for scene in program.scenes],
        "endings": [emit_ending(ending) for ending in program.endings],
    }
    return story


def emit_speaker(speaker):
    obj = {"id": speaker.name.value, "name": speaker.label.value}
    if speaker.portrait is not None:
        obj["portrait"] = speaker.portrait.value
    return obj


def emit_item(item):
    return {"id": item.name.value, "name": item.label.value}


def emit_variable(variable):
    return {"id": variable.name.value, "type": variable.kind, "value": variable.value}


def emit_scene(scene):
    obj = {"id": scene.name.value}
    if scene.background is not None:
        obj["background"] = scene.background.value
    obj["body"] = [emit_step(step) for step in scene.body]
    obj["choices"] = [emit_choice(choice) for choice in scene.choices]
    return obj


def emit_ending(ending):
    return {
        "id": ending.name.value,
        "outcome": ending.outcome.value,
        "text": ending.text.value,
    }


def emit_step(step):
    if isinstance(step, Narration):
        return {"text": step.text.value}
    if isinstance(step, Dialogue):
        return {"speaker": step.speaker.value, "text": step.text.value}
    if isinstance(step, Conditional):
        obj = {
            "if": emit_test(step.test),
            "then": [emit_step(inner) for inner in step.then_steps],
        }
        if step.else_steps is not None:
            obj["else"] = [emit_step(inner) for inner in step.else_steps]
        return obj
    if isinstance(step, Change):
        return emit_change(step)
    raise TypeError(f"unknown step {type(step).__name__}")


def emit_test(test):
    if isinstance(test, Has):
        return {"has": test.name.value}
    if isinstance(test, Lacks):
        return {"lacks": test.name.value}
    if isinstance(test, Is):
        return {"is": test.name.value, "value": test.value}
    if isinstance(test, Compare):
        return {"compare": test.name.value, "op": test.op.value, "value": test.number.value}
    raise TypeError(f"unknown test {type(test).__name__}")


def emit_change(change):
    if change.kind == "give":
        return {"give": change.name.value}
    if change.kind == "take":
        return {"take": change.name.value}
    if change.kind == "set":
        if change.value_token.kind == "number":
            value = change.value_token.value
        else:
            value = change.value_token.value == "true"
        return {"set": change.name.value, "value": value}
    if change.kind == "increase":
        return {"increase": change.name.value, "by": change.by_token.value}
    if change.kind == "decrease":
        return {"decrease": change.name.value, "by": change.by_token.value}
    raise TypeError(f"unknown change {change.kind}")


def emit_choice(choice):
    obj = {"text": choice.text.value}
    if choice.when is not None:
        obj["when"] = emit_test(choice.when)
    if choice.changes:
        obj["changes"] = [emit_change(change) for change in choice.changes]
    if choice.dest.kind == "scene":
        obj["to"] = {"scene": choice.dest.name.value}
    else:
        obj["to"] = {"ending": choice.dest.name.value}
    return obj


def dumps(story):
    return json.dumps(story, indent=2, ensure_ascii=False) + "\n"