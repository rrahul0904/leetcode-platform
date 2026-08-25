"""Fail-closed compatibility patches for attachment-backed executable questions."""

from .execution import LocalFunctionalPythonRunner

_OLD = '''def invoke(function, value):
    if payload["entrypoint"] == "solve":
        return function(value)
    if not isinstance(value, dict):
        return function(value)
    parameters = inspect.signature(function).parameters
    kwargs = {}
    aliases = {"max_rows_per_batch": "capacity", "max_capacity": "capacity"}
    for name in parameters:
        source_name = name if name in value else aliases.get(name)
        if source_name is None or source_name not in value:
            raise TypeError("test input does not provide the required function arguments")
        kwargs[name] = value[source_name]
    return function(**kwargs)
'''

_NEW = '''def invoke(function, value):
    if not isinstance(value, dict):
        return function(value)
    parameters = inspect.signature(function).parameters
    # A single-argument question may intentionally receive an object as its value.
    if len(parameters) == 1:
        only = next(iter(parameters))
        if only not in value:
            return function(value)
    kwargs = {}
    aliases = {"max_rows_per_batch": "capacity", "max_capacity": "capacity"}
    for name in parameters:
        source_name = name if name in value else aliases.get(name)
        if source_name is None or source_name not in value:
            raise TypeError("test input does not provide the required function arguments")
        kwargs[name] = value[source_name]
    return function(**kwargs)
'''

current_harness = LocalFunctionalPythonRunner._HARNESS
if _OLD not in current_harness:
    raise RuntimeError("Python runner harness changed; attachment execution patch must be reviewed")

# setattr avoids narrowing the class attribute to its original Literal type in Pyright.
setattr(LocalFunctionalPythonRunner, "_HARNESS", current_harness.replace(_OLD, _NEW))
