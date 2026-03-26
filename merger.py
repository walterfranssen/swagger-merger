#!/usr/bin/env python3
import argparse
import copy
import json
from pathlib import Path
from typing import Any

import requests
import yaml


COMPONENT_BUCKETS = [
    "schemas",
    "responses",
    "parameters",
    "examples",
    "requestBodies",
    "headers",
    "securitySchemes",
    "links",
    "callbacks",
]


def load_yaml_or_json(content: str) -> dict[str, Any]:
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError:
        return json.loads(content)


def read_openapi_document(source: str, timeout_seconds: int) -> dict[str, Any]:
    if source.startswith("http://") or source.startswith("https://"):
        response = requests.get(source, timeout=timeout_seconds)
        response.raise_for_status()
        return load_yaml_or_json(response.text)

    with open(source, "r", encoding="utf-8") as file:
        return load_yaml_or_json(file.read())


def prefixed_path(path_prefix: str | None, raw_path: str) -> str:
    if not path_prefix:
        return raw_path

    normalized_prefix = "/" + path_prefix.strip("/")
    if raw_path == "/":
        return normalized_prefix

    return normalized_prefix + raw_path


def ensure_openapi(spec: dict[str, Any], service_name: str) -> None:
    if not isinstance(spec, dict):
        raise ValueError(f"Service '{service_name}' did not resolve to an object.")

    if "openapi" not in spec and "swagger" not in spec:
        raise ValueError(f"Service '{service_name}' does not look like an OpenAPI/Swagger document.")


def merge_components(
    merged: dict[str, Any],
    service_spec: dict[str, Any],
    service_name: str,
) -> None:
    source_components = service_spec.get("components") or {}
    if not source_components:
        return

    merged.setdefault("components", {})

    for bucket in COMPONENT_BUCKETS:
        incoming_items = source_components.get(bucket) or {}
        if not incoming_items:
            continue

        target_bucket = merged["components"].setdefault(bucket, {})

        for component_name, component_value in incoming_items.items():
            if component_name not in target_bucket:
                target_bucket[component_name] = copy.deepcopy(component_value)
                continue

            if target_bucket[component_name] != component_value:
                raise ValueError(
                    "Component collision detected for "
                    f"components.{bucket}.{component_name} while merging service '{service_name}'."
                )


def merge_tags(merged: dict[str, Any], service_spec: dict[str, Any]) -> None:
    incoming_tags = service_spec.get("tags") or []
    if not incoming_tags:
        return

    existing_tags = merged.setdefault("tags", [])
    existing_names = {tag.get("name") for tag in existing_tags if isinstance(tag, dict)}

    for tag in incoming_tags:
        if not isinstance(tag, dict):
            continue

        tag_name = tag.get("name")
        if tag_name not in existing_names:
            existing_tags.append(copy.deepcopy(tag))
            existing_names.add(tag_name)


def merge_security_requirements(merged: dict[str, Any], service_spec: dict[str, Any]) -> None:
    incoming = service_spec.get("security") or []
    if not incoming:
        return

    merged_security = merged.setdefault("security", [])
    for sec in incoming:
        if sec not in merged_security:
            merged_security.append(copy.deepcopy(sec))


def merge_paths(
    merged: dict[str, Any],
    service_spec: dict[str, Any],
    service_name: str,
    path_prefix: str | None,
) -> None:
    incoming_paths = service_spec.get("paths") or {}
    if not incoming_paths:
        return

    merged_paths = merged.setdefault("paths", {})

    for raw_path, path_item in incoming_paths.items():
        target_path = prefixed_path(path_prefix, raw_path)

        if target_path in merged_paths and merged_paths[target_path] != path_item:
            raise ValueError(
                f"Path collision detected for '{target_path}' while merging service '{service_name}'."
            )

        merged_paths[target_path] = copy.deepcopy(path_item)


def load_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("Config root must be a YAML/JSON object.")

    if "services" not in config or not isinstance(config["services"], list):
        raise ValueError("Config must contain a 'services' list.")

    return config


def merge_from_config(config: dict[str, Any]) -> dict[str, Any]:
    openapi_version = config.get("openapi", "3.0.3")
    info = config.get("info") or {
        "title": "Merged OpenAPI",
        "version": "1.0.0",
    }

    merged: dict[str, Any] = {
        "openapi": openapi_version,
        "info": info,
        "paths": {},
    }

    if config.get("servers"):
        merged["servers"] = copy.deepcopy(config["servers"])

    timeout_seconds = int(config.get("http_timeout_seconds", 15))

    for index, service in enumerate(config["services"], start=1):
        if not isinstance(service, dict):
            raise ValueError(f"services[{index}] must be an object.")

        service_name = service.get("name") or f"service-{index}"
        source = service.get("source")
        if not source:
            raise ValueError(f"Service '{service_name}' is missing required field: source")

        service_spec = read_openapi_document(source=source, timeout_seconds=timeout_seconds)
        ensure_openapi(service_spec, service_name)

        merge_paths(
            merged=merged,
            service_spec=service_spec,
            service_name=service_name,
            path_prefix=service.get("path_prefix"),
        )
        merge_components(merged=merged, service_spec=service_spec, service_name=service_name)
        merge_tags(merged=merged, service_spec=service_spec)
        merge_security_requirements(merged=merged, service_spec=service_spec)

    return merged


def write_output(spec: dict[str, Any], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as file:
        yaml.safe_dump(spec, file, sort_keys=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge OpenAPI specs into a single Swagger/OpenAPI document.")
    parser.add_argument("--config", required=True, help="Path to merger config YAML/JSON file.")
    parser.add_argument("--output", default="./merged-openapi.yaml", help="Path for merged output file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    merged = merge_from_config(config)
    write_output(merged, args.output)
    print(f"Merged spec written to {args.output}")


if __name__ == "__main__":
    main()
