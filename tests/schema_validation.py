from __future__ import annotations

import json
import re


def resolve_ref(schema_root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise AssertionError(f"Unsupported schema reference: {ref}")

    resolved = schema_root
    for part in ref[2:].split("/"):
        resolved = resolved[part]
    return resolved


def validate_instance(instance: object, schema: dict, schema_root: dict, path: str = "$") -> None:
    if "$ref" in schema:
        validate_instance(instance, resolve_ref(schema_root, schema["$ref"]), schema_root, path)
        return

    if "oneOf" in schema:
        errors = []
        for candidate in schema["oneOf"]:
            try:
                validate_instance(instance, candidate, schema_root, path)
                return
            except AssertionError as error:
                errors.append(str(error))
        raise AssertionError(f"{path} does not satisfy any oneOf schema: {'; '.join(errors)}")

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(instance, dict):
            raise AssertionError(f"{path} expected object")
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                raise AssertionError(f"{path} missing required key: {key}")

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                validate_instance(value, properties[key], schema_root, f"{path}.{key}")
            elif additional is False:
                raise AssertionError(f"{path} has unexpected key: {key}")
            elif isinstance(additional, dict):
                validate_instance(value, additional, schema_root, f"{path}.{key}")
        return

    if expected_type == "array":
        if not isinstance(instance, list):
            raise AssertionError(f"{path} expected array")
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            raise AssertionError(f"{path} expected at least {min_items} items")
        if schema.get("uniqueItems"):
            serialized = [json.dumps(item, sort_keys=True) for item in instance]
            if len(serialized) != len(set(serialized)):
                raise AssertionError(f"{path} expected unique items")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(instance):
                validate_instance(item, item_schema, schema_root, f"{path}[{index}]")
        return

    if expected_type == "string":
        if not isinstance(instance, str):
            raise AssertionError(f"{path} expected string")
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            raise AssertionError(f"{path} expected minLength {min_length}")
        pattern = schema.get("pattern")
        if pattern is not None and re.match(pattern, instance) is None:
            raise AssertionError(f"{path} did not match pattern {pattern}")
    elif expected_type == "boolean":
        if not isinstance(instance, bool):
            raise AssertionError(f"{path} expected boolean")

    enum = schema.get("enum")
    if enum is not None and instance not in enum:
        raise AssertionError(f"{path} expected one of {enum}")