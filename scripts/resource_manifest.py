"""Generate and validate deterministic resource manifests for local skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path, PureWindowsPath


SCHEMA_VERSION = 3
TEXT_HASH_EXTENSIONS = frozenset(
    {
        ".md", ".txt", ".py", ".ps1", ".sh", ".csx", ".cs", ".svg",
        ".xml", ".json", ".yaml", ".yml", ".toml", ".csv", ".tsv",
        ".html", ".css", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
        # Lua resources (skill filters) must hash newline-normalised as well,
        # otherwise the recorded hash depends on the checkout's CRLF settings.
        ".lua",
    }
)
TEXT_HASH_NAMES = frozenset({".gitignore", ".gitattributes", ".editorconfig", ".env"})
RESOURCE_DIRECTORIES = (
    "scripts", "references", "resources", "assets", "examples", "prompts", "agents",
)
IGNORED_DIRECTORIES = frozenset(
    {
        "__pycache__", ".ruff_cache", ".pytest_cache", ".jules", ".venv",
        ".venv_test", "node_modules", "_runtime", "garmin-output", "output",
        "outputs", "scratch", "tmp", "temp", "dist", "build", "tasks",
    }
)
IGNORED_FILE_NAMES = frozenset({"garmin_tokens.json"})
LOCAL_REFERENCE_RE = re.compile(
    r"""(?P<path>(?<![A-Za-z])(?:\.\.[\\/])*(?:(?:scripts|references|resources|assets|examples|prompts|agents)[\\/][^\s`"'<>]+|[A-Za-z0-9._-]+[\\/](?:SKILL\.md|skill\.json|(?:scripts|references|resources|assets|examples|prompts|agents)[\\/][^\s`"'<>]+)))"""
)
KNOWN_SUFFIX_RE = re.compile(
    r"(?P<stable>.*?(?:SKILL\.md|\.md|\.json|\.py|\.ps1|\.sh|\.csx|\.cs|\.svg|\.png|\.jpg|\.jpeg|\.gif|\.pptx|\.docx|\.pdf|\.txt|\.yaml|\.yml|\.toml|\.csv|\.tsv|\.html|\.css|\.js|\.ts|\.tsx|\.jsx))",
    re.IGNORECASE,
)


class ManifestContractError(RuntimeError):
    """Raised when a skill cannot produce a safe manifest."""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ManifestContractError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def canonical_sha256(path: Path) -> str:
    data = path.read_bytes()
    name = path.name.lower()
    if (
        path.suffix.lower() in TEXT_HASH_EXTENSIONS
        or name in TEXT_HASH_NAMES
        or name.startswith(".env.")
    ):
        text = data.decode("utf-8")
        data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _portable_relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if not _is_within(resolved, root_resolved):
        raise ManifestContractError("resolved dependency escapes the skills root")
    return resolved.relative_to(root_resolved).as_posix()


def _normalize_reference(raw: str) -> str:
    value = raw.replace("\\", "/").strip()
    if value.lower().startswith("skills/"):
        value = value[7:]
    if value.lower().startswith("skill_root/"):
        value = value[len("skill_root/"):]
    value = re.sub(r"\]\(.*$", "", value)
    value = re.sub(r"[\)\]\.,;:\*]+$", "", value)
    match = KNOWN_SUFFIX_RE.match(value)
    return (match.group("stable") if match else value).replace("\\", "/")


def _ignore_reference(value: str) -> bool:
    if not value or value.lower().startswith("tmp/"):
        return True
    if bool(re.search(r"\[.+?\]|\{.+?\}|<.+?>", value)):
        return True
    return KNOWN_SUFFIX_RE.fullmatch(value) is None


def _validate_declared_path(value: str) -> None:
    if PureWindowsPath(value).is_absolute() or value.startswith(("/", "\\")):
        raise ManifestContractError(f"non-portable dependency path: {value}")


def _resolve_reference(root: Path, skill_dir: Path, value: str) -> dict[str, object]:
    _validate_declared_path(value)
    relative = Path(*value.split("/"))
    resolved: Path | None = None
    # Explicit parent references follow Pi's skill-relative rule, without the
    # historical library-root fallback retained for existing schema-v3 indexes.
    candidates = (skill_dir / relative,) if ".." in relative.parts else (skill_dir / relative, root / relative)
    for candidate in candidates:
        candidate_resolved = candidate.resolve()
        if not _is_within(candidate_resolved, root.resolve()):
            raise ManifestContractError(f"dependency escapes root: {value}")
        if candidate.is_file():
            resolved = candidate_resolved
            break
    # Schema v3 stores portable index paths, not verbatim source spelling.
    # Canonicalising parent refs preserves existing shared-resource indexes.
    declared_path = _portable_relative(skill_dir / relative, root) if ".." in relative.parts else value
    return {
        "path": declared_path,
        "exists": resolved is not None,
        "resolved_path": _portable_relative(resolved, root) if resolved else None,
        "sha256": canonical_sha256(resolved) if resolved else None,
    }


def declared_dependencies(root: Path, skill_dir: Path, text: str) -> list[dict[str, object]]:
    dependencies: list[dict[str, object]] = []
    seen: set[tuple[object, object]] = set()
    for match in LOCAL_REFERENCE_RE.finditer(text):
        value = _normalize_reference(match.group("path"))
        if _ignore_reference(value):
            continue
        dependency = _resolve_reference(root, skill_dir, value)
        identity = (dependency["path"], dependency["resolved_path"])
        if identity in seen:
            continue
        seen.add(identity)
        dependencies.append(dependency)
    return sorted(dependencies, key=lambda item: str(item["path"]).lower())


def _ignore_file(path: Path) -> bool:
    lower = path.name.lower()
    return (
        lower in IGNORED_FILE_NAMES
        or lower in {"resource-manifest.json", "skill.json"}
        or lower.endswith((".bak", ".log", ".pyc", ".pyo"))
        or ".bak_" in lower
        or ".bak-" in lower
        or (lower.startswith("resource-manifest.") and lower.endswith(".tmp"))
    )


def _resource_file_count(skill_dir: Path, directory: Path) -> int:
    count = 0
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ManifestContractError(
                f"symbolic links are not allowed in skill resources: {path.relative_to(skill_dir).as_posix()}"
            )
        if not path.is_file() or _ignore_file(path):
            continue
        relative_parts = path.relative_to(directory).parts
        if any(part in IGNORED_DIRECTORIES for part in relative_parts[:-1]):
            continue
        if not _is_within(path.resolve(), skill_dir.resolve()):
            raise ManifestContractError(
                f"resource file escapes skill: {path.relative_to(skill_dir).as_posix()}"
            )
        count += 1
    return count


def _resource_file_hashes(root: Path, skill_dir: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for directory in skill_dir.iterdir():
        if directory.is_symlink():
            raise ManifestContractError(
                f"symbolic links are not allowed in skill resources: {directory.name}"
            )
        if not directory.is_dir() or directory.name in IGNORED_DIRECTORIES:
            continue
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ManifestContractError(
                    f"symbolic links are not allowed in skill resources: {path.relative_to(skill_dir).as_posix()}"
                )
            if not path.is_file() or _ignore_file(path):
                continue
            relative_parts = path.relative_to(directory).parts
            if any(part in IGNORED_DIRECTORIES for part in relative_parts[:-1]):
                continue
            if not _is_within(path.resolve(), skill_dir.resolve()):
                raise ManifestContractError(
                    f"resource file escapes skill: {path.relative_to(skill_dir).as_posix()}"
                )
            files.append(
                {
                    "path": path.relative_to(skill_dir).as_posix(),
                    "sha256": canonical_sha256(path),
                }
            )
    return sorted(files, key=lambda item: item["path"].lower())


def expected_manifest(root: Path, skill_dir: Path, generated_at: str) -> dict[str, object]:
    root = root.resolve()
    skill_dir = skill_dir.resolve()
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file() or not _is_within(skill_file.resolve(), root):
        raise ManifestContractError("SKILL.md is missing or outside the skills root")
    text = skill_file.read_text(encoding="utf-8")
    dependencies = declared_dependencies(root, skill_dir, text)
    missing = [str(item["path"]) for item in dependencies if not item["exists"]]
    if missing:
        raise ManifestContractError("missing declared dependencies: " + ", ".join(missing))
    top_level_files: list[str] = []
    for path in skill_dir.iterdir():
        if path.is_symlink():
            raise ManifestContractError(f"symbolic links are not allowed: {path.name}")
        if path.is_file() and not _ignore_file(path):
            top_level_files.append(path.name)
    top_level_files.sort()
    for name in top_level_files:
        if not _is_within((skill_dir / name).resolve(), root):
            raise ManifestContractError(f"top-level file escapes root: {name}")
    top_level_file_hashes = [
        {"path": name, "sha256": canonical_sha256(skill_dir / name)}
        for name in top_level_files
    ]
    top_level_directories = sorted(
        path.name for path in skill_dir.iterdir()
        if path.is_dir() and path.name not in IGNORED_DIRECTORIES
    )
    resource_directories = [
        {"name": name, "file_count": _resource_file_count(skill_dir, skill_dir / name)}
        for name in RESOURCE_DIRECTORIES if (skill_dir / name).is_dir()
    ]
    resource_file_hashes = _resource_file_hashes(root, skill_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": skill_dir.name,
        "generated_at": generated_at,
        "hash_algorithm": "SHA-256",
        "text_hash_normalization": "LF",
        "skill_md": "SKILL.md",
        "skill_md_sha256": canonical_sha256(skill_file),
        "top_level_files": top_level_files,
        "top_level_file_hashes": top_level_file_hashes,
        "top_level_directories": top_level_directories,
        "resource_directories": resource_directories,
        "resource_file_hashes": resource_file_hashes,
        "declared_local_dependencies": dependencies,
        "missing_declared_dependencies": [],
    }


def _semantic_manifest(document: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in document.items() if key != "generated_at"}


def _valid_generated_at(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _load_manifest(path: Path) -> dict[str, object]:
    document = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object
    )
    if not isinstance(document, dict):
        raise ManifestContractError("manifest root must be an object")
    return document


def validate_manifest(root: Path, skill_dir: Path) -> list[dict[str, str]]:
    manifest_path = skill_dir / "resource-manifest.json"
    issues: list[dict[str, str]] = []
    if not manifest_path.is_file():
        return [{"code": "manifest_missing", "detail": "resource-manifest.json is missing"}]
    try:
        actual = _load_manifest(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ManifestContractError) as exc:
        return [{"code": "manifest_parse_error", "detail": str(exc)}]
    generated_at_value = actual.get("generated_at")
    if isinstance(generated_at_value, str) and _valid_generated_at(generated_at_value):
        generated_at = generated_at_value
    else:
        issues.append({"code": "generated_at_invalid", "detail": "generated_at is not ISO-8601"})
        generated_at = "1970-01-01T00:00:00"
    try:
        expected = expected_manifest(root, skill_dir, generated_at)
    except (OSError, UnicodeError, ManifestContractError) as exc:
        issues.append({"code": "manifest_source_error", "detail": str(exc)})
        return issues
    for key, expected_value in _semantic_manifest(expected).items():
        if actual.get(key) != expected_value:
            issues.append({"code": f"{key}_mismatch", "detail": f"{key} differs from disk"})
    extra = sorted(set(actual) - set(expected))
    if extra:
        issues.append({"code": "unexpected_fields", "detail": ", ".join(extra)})
    dependencies = actual.get("declared_local_dependencies", []) or []
    if not isinstance(dependencies, list):
        issues.append({"code": "dependency_invalid", "detail": "dependency list is invalid"})
        dependencies = []
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            issues.append({"code": "dependency_invalid", "detail": "dependency must be an object"})
            continue
        for key in ("path", "resolved_path"):
            value = dependency.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                issues.append({"code": "dependency_path_invalid", "detail": f"{key} is not text"})
                continue
            if (
                PureWindowsPath(value).is_absolute() or value.startswith(("/", "\\"))
                or ".." in Path(value.replace("\\", "/")).parts
            ):
                issues.append({"code": "dependency_path_nonportable", "detail": f"{key} is not portable"})
    return issues


def iter_skill_dirs(
    root: Path,
    include_skills: Iterable[str] = (),
    exclude_skills: Iterable[str] = (),
) -> list[Path]:
    root = root.resolve()
    all_skills = {
        path.name: path for path in root.iterdir()
        if path.is_dir()
        and path.name not in {".system", "scripts", "shared", "reports", "examples"}
        and (path / "SKILL.md").is_file()
    }
    includes = {item for item in include_skills if item}
    excludes = {item for item in exclude_skills if item}
    unknown_includes = sorted(includes - set(all_skills))
    unknown_excludes = sorted(excludes - set(all_skills))
    overlap = sorted(includes & excludes)
    if unknown_includes:
        raise ManifestContractError("unknown included skills: " + ", ".join(unknown_includes))
    if unknown_excludes:
        raise ManifestContractError("unknown excluded skills: " + ", ".join(unknown_excludes))
    if overlap:
        raise ManifestContractError("skills cannot be both included and excluded: " + ", ".join(overlap))
    names = sorted(includes or set(all_skills))
    selected = [all_skills[name] for name in names if name not in excludes]
    if (includes or excludes) and not selected:
        raise ManifestContractError("skill selection is empty")
    return selected


def check_manifests(
    root: Path,
    include_skills: Iterable[str] = (),
    exclude_skills: Iterable[str] = (),
) -> dict[str, object]:
    try:
        skill_dirs = iter_skill_dirs(root, include_skills, exclude_skills)
    except ManifestContractError as exc:
        return {"checked": 0, "stale": 1, "stale_skills": [], "issues": [{"skill": "", "code": "scope_error", "detail": str(exc)}]}
    issues: list[dict[str, str]] = []
    stale_skills: list[str] = []
    for skill_dir in skill_dirs:
        skill_issues = validate_manifest(root, skill_dir)
        if skill_issues:
            stale_skills.append(skill_dir.name)
            issues.extend({"skill": skill_dir.name, **issue} for issue in skill_issues)
    return {"checked": len(skill_dirs), "stale": len(stale_skills), "stale_skills": stale_skills, "issues": issues}


def generate_manifests(
    root: Path,
    include_skills: Iterable[str] = (),
    exclude_skills: Iterable[str] = (),
) -> dict[str, object]:
    try:
        skill_dirs = iter_skill_dirs(root, include_skills, exclude_skills)
    except ManifestContractError as exc:
        return {"checked": 0, "written": 0, "unchanged": 0, "failed": 1, "issues": [{"skill": "", "detail": str(exc)}]}
    written = 0
    unchanged = 0
    issues: list[dict[str, str]] = []
    pending: list[tuple[Path, dict[str, object]]] = []
    for skill_dir in skill_dirs:
        manifest_path = skill_dir / "resource-manifest.json"
        actual: dict[str, object] | None = None
        if manifest_path.is_file():
            try:
                actual = _load_manifest(manifest_path)
            except (OSError, UnicodeError, json.JSONDecodeError, ManifestContractError):
                actual = None
        try:
            comparison_time = (
                str(actual.get("generated_at"))
                if actual and isinstance(actual.get("generated_at"), str)
                else "1970-01-01T00:00:00"
            )
            candidate = expected_manifest(root, skill_dir, comparison_time)
        except (OSError, UnicodeError, ManifestContractError) as exc:
            issues.append({"skill": skill_dir.name, "detail": str(exc)})
            continue
        if (
            actual is not None
            and _valid_generated_at(actual.get("generated_at"))
            and _semantic_manifest(actual) == _semantic_manifest(candidate)
        ):
            unchanged += 1
            continue
        candidate["generated_at"] = datetime.now().astimezone().replace(microsecond=0).isoformat()
        pending.append((manifest_path, candidate))

    if issues:
        return {
            "checked": len(skill_dirs),
            "written": 0,
            "unchanged": unchanged,
            "failed": len(issues),
            "issues": issues,
        }

    for manifest_path, candidate in pending:
        payload = json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix="resource-manifest.", suffix=".tmp", dir=manifest_path.parent
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, manifest_path)
            written += 1
        except OSError as exc:
            issues.append({"skill": manifest_path.parent.name, "detail": f"atomic manifest write failed: {exc}"})
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
    return {"checked": len(skill_dirs), "written": written, "unchanged": unchanged, "failed": len(issues), "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "check"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--include-skill", action="append", default=[])
    parser.add_argument("--exclude-skill", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "generate":
        result = generate_manifests(root, args.include_skill, args.exclude_skill)
        failed_value = result["failed"]
    else:
        result = check_manifests(root, args.include_skill, args.exclude_skill)
        failed_value = result["stale"]
    failed = failed_value if isinstance(failed_value, int) else 1
    print(
        json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        if args.json else json.dumps(result, ensure_ascii=False, indent=2)
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
