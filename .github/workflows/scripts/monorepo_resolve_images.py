#!/usr/bin/env python3
"""Resolve each module image: this-run tag, else GHCR tag, else modules.yaml fallback."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

MODULES = (
    ("backend", "qubership-apihub-backend"),
    ("ui", "qubership-apihub-ui"),
    ("build_task_consumer", "qubership-apihub-build-task-consumer"),
    ("api_linter_service", "qubership-api-linter-service"),
    ("agents_backend", "qubership-apihub-agents-backend"),
)


def ghcr_exists(repository: str, tag: str, actor: str, token: str) -> bool:
    owner_name = repository.split("/", 3)[-1] if repository.startswith("ghcr.io/") else repository
    if "/" not in owner_name:
        return False
    scope = urllib.parse.quote(f"repository:{owner_name}:pull")
    auth = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    auth.add_password(None, "https://ghcr.io/token", actor, token)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(auth))
    try:
        with opener.open(f"https://ghcr.io/token?service=ghcr.io&scope={scope}", timeout=30) as resp:
            pull_token = json.loads(resp.read().decode("utf-8")).get("token", "")
    except urllib.error.URLError:
        return False
    req = urllib.request.Request(
        f"https://ghcr.io/v2/{owner_name}/manifests/{urllib.parse.quote(tag)}",
        method="HEAD",
        headers={
            "Authorization": f"Bearer {pull_token}",
            "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as err:
        return err.code == 200
    except urllib.error.URLError:
        return False


def fallback_from_modules(modules_file: str) -> tuple[str, str]:
    env_registry = os.environ.get("FALLBACK_REGISTRY", "")
    env_tag = os.environ.get("FALLBACK_TAG", "")
    if env_registry and env_tag:
        return env_registry, env_tag
    owner = os.environ.get("REGISTRY_OWNER", "")
    default_registry = f"ghcr.io/{owner}" if owner else "ghcr.io/netcracker"
    default_tag = os.environ.get("CURRENT_TAG", "dev")
    if yaml is None or not Path(modules_file).is_file():
        return default_registry, default_tag
    cfg = yaml.safe_load(Path(modules_file).read_text(encoding="utf-8")) or {}
    e2e = cfg.get("e2e") or {}
    return (
        e2e.get("fallback_registry") or default_registry,
        e2e.get("fallback_tag") or default_tag,
    )


def main() -> int:
    actor = os.environ["GITHUB_ACTOR"]
    token = os.environ["GITHUB_TOKEN"]
    owner = os.environ["REGISTRY_OWNER"]
    fallback_registry, fallback_tag = fallback_from_modules(os.environ.get("MODULES_FILE", "ci/modules.yaml"))
    current_tag = os.environ["CURRENT_TAG"]
    built = json.loads(os.environ.get("BUILT_JSON", "{}"))
    print(f"fallback={fallback_registry} tag={fallback_tag} current={current_tag}")
    refs = {}
    for key, image_name in MODULES:
        built_tag = built.get(key) or ""
        repo = f"ghcr.io/{owner}/{image_name}"
        if built_tag:
            refs[key] = f"{repo}:{built_tag}"
            continue
        if ghcr_exists(repo, current_tag, actor, token):
            refs[key] = f"{repo}:{current_tag}"
            continue
        refs[key] = f"{fallback_registry}/{image_name}:{fallback_tag}"
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        for key, ref in refs.items():
            fh.write(f"{key}_image={ref}\n")
        fh.write(f"image_refs_json={json.dumps(refs)}\n")
    print(json.dumps(refs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
