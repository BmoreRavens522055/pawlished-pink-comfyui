"""Read-only API graph socket checks. Never queues inference or rewrites a graph."""

from pathlib import Path


def check(graph, schema, input_root=None):
    if "prompt" in graph and isinstance(graph["prompt"], dict):
        graph = graph["prompt"]
    if (
        not isinstance(graph, dict)
        or not graph
        or any(not isinstance(n, dict) or "class_type" not in n for n in graph.values())
    ):
        return [
            "NOT_API_GRAPH: UI workflow needs ComfyUI loading, not invented conversion"
        ]
    errors = []
    edges = {str(k): [] for k in graph}

    def edge(node, key, value, expected):
        if not (
            isinstance(value, list)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], int)
        ):
            return False
        source, index = value
        if source not in graph:
            errors.append(f"{node}.{key}: missing source {source}")
            return True
        outputs = schema.get(graph[source]["class_type"], {}).get("output", [])
        if index < 0 or index >= len(outputs):
            errors.append(f"{node}.{key}: invalid output index")
        elif expected not in ("*", outputs[index]) and not isinstance(expected, list):
            errors.append(
                f"{node}.{key}: {outputs[index]} cannot connect to {expected}"
            )
        edges[node].append(source)
        return True

    for node, n in graph.items():
        spec = schema.get(n["class_type"])
        if spec is None:
            errors.append(f'{node}: unknown class {n["class_type"]}')
            continue
        inputs = n.get("inputs", {})
        required = dict(spec.get("input", {}).get("required", {}))
        optional = dict(spec.get("input", {}).get("optional", {}))
        # Pinned Comfy V3 serializes Autogrow sockets as group.name, not a nested JSON map.
        for group, definition in list({**required, **optional}.items()):
            if definition[0] == "COMFY_AUTOGROW_V3":
                template = definition[1]["template"]
                item = next(iter(template["input"]["required"].values()))
                required.pop(group, None)
                optional.pop(group, None)
                names = template.get("names") or [
                    template["prefix"] + str(i) for i in range(template["max"])
                ]
                for i, name in enumerate(names):
                    (required if i < template.get("min", 0) else optional)[
                        group + "." + name
                    ] = item
        for key in required:
            if key not in inputs:
                errors.append(f"{node}.{key}: required input absent")
        for key, value in inputs.items():
            definition = {**required, **optional}.get(key)
            if definition is None:
                # VHS format-specific controls and dynamic V3 sockets require native validation.
                errors.append(
                    f"{node}.{key}: schema does not describe input; native validation required"
                )
                continue
            expected = definition[0]
            options = definition[1] if len(definition) > 1 else {}
            if edge(node, key, value, expected):
                continue
            if expected in (
                "MODEL",
                "VAE",
                "CLIP",
                "CONDITIONING",
                "LATENT",
                "IMAGE",
                "AUDIO",
                "VIDEO",
            ):
                errors.append(f"{node}.{key}: connection required")
            choices = expected if isinstance(expected, list) else options.get("options")
            if choices and value not in choices:
                errors.append(f"{node}.{key}: value absent from current options")
            if input_root and n["class_type"] == "LoadImage" and key == "image":
                p = Path(input_root) / str(value)
                if (
                    not p.resolve().is_relative_to(Path(input_root).resolve())
                    or not p.is_file()
                ):
                    errors.append(f"{node}.{key}: missing or unsafe image path")
    visited = set()
    visiting = set()

    def visit(node):
        if node in visiting:
            errors.append("graph contains a cycle")
            return
        if node in visited:
            return
        visiting.add(node)
        for source in edges[node]:
            visit(source)
        visiting.remove(node)
        visited.add(node)

    for node in edges:
        visit(node)
    return errors


def native_audio_path(graph):
    """Narrow diagnostic, not proof of sound, conditioning intent or model compatibility."""
    decoders = {
        k
        for k, n in graph.items()
        if n.get("class_type") in ("VAEDecodeAudio", "VAEDecodeAudioTiled")
    }
    for n in graph.values():
        if n.get("class_type") in ("CreateVideo", "VHS_VideoCombine"):
            link = n.get("inputs", {}).get("audio")
            if isinstance(link, list) and link[0] in decoders:
                return True
    return False
