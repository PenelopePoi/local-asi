#!/usr/bin/env python3
"""
Teacher Knowledge Snapshot — bundle the accumulating state into one zip.

What it includes:
  - ~/.claude/skills/                                (skill library)
  - ~/local-asi/knowledge/                           (KB + skill-writes audit)
  - ~/local-asi/asi.py, mcp-server.py, *.md          (config + docs)
  - ~/Teacher/.prompts/ if the Teacher clone exists  (Weatherspoon prompts)
  - ~/Teacher/CLAUDE.md if present                   (project-level config)

What it does NOT include:
  - node_modules, __pycache__, .git, Theia lib/ builds, .DS_Store
  - keys, tokens, ~/.claude.json (which carries MCP credentials)

Output:
  ~/teacher-snapshots/teacher-snapshot-YYYYMMDD-HHMMSS.zip

Encryption: intentionally omitted. Use a filesystem-level encrypted
volume or wrap the zip yourself. Better to ship zero crypto than
half-baked crypto.

Env overrides (optional):
  TEACHER_SNAPSHOT_DIR   — output directory (default ~/teacher-snapshots)
  TEACHER_SNAPSHOT_KEEP  — how many snapshots to keep (default 14)
"""

import json
import os
import sys
import time
import zipfile
import datetime
from pathlib import Path

HOME = Path.home()

# ============================================================
# Sources to bundle
# ============================================================

SOURCES = [
    {
        "arcname": "skills-library",
        "path":    HOME / ".claude" / "skills",
        "required": False,
    },
    {
        "arcname": "knowledge",
        "path":    HOME / "local-asi" / "knowledge",
        "required": True,
    },
    {
        "arcname": "local-asi",
        "path":    HOME / "local-asi",
        "required": True,
        "files_only": ["asi.py", "mcp-server.py", "README.md",
                       "export-snapshot.py", "detect-anomalies.py",
                       "install-cron.sh"],
    },
    {
        "arcname": "teacher-prompts",
        "path":    HOME / "Teacher" / ".prompts",
        "required": False,
    },
    {
        "arcname": "teacher-config",
        "path":    HOME / "Teacher" / "CLAUDE.md",
        "required": False,
    },
]

EXCLUDED_DIRS = {"__pycache__", "node_modules", ".git", "lib", "dist",
                 ".next", ".turbo", "coverage", ".nyc_output", ".pytest_cache",
                 ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".log", ".tsbuildinfo"}


def _name_blocked(name: str) -> bool:
    if name in EXCLUDED_DIRS:
        return True
    if name.startswith(".DS_"):
        return True
    return False


def _path_skip(path: Path) -> bool:
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    for part in path.parts:
        if _name_blocked(part):
            return True
    return False


def iter_files(source: dict):
    base = source["path"]
    if not base.exists():
        return
    if base.is_file():
        yield base, base.name
        return

    allow = source.get("files_only")
    if allow:
        for name in allow:
            f = base / name
            if f.is_file():
                yield f, name
        return

    for p in base.rglob("*"):
        if _path_skip(p):
            continue
        if p.is_file() and not p.is_symlink():
            try:
                rel = p.relative_to(base)
            except ValueError:
                continue
            yield p, str(rel)


def build_manifest(files_added: list, started: float) -> dict:
    return {
        "tool":           "teacher-snapshot",
        "version":        1,
        "started_utc":    datetime.datetime.utcfromtimestamp(started).isoformat() + "Z",
        "finished_utc":   datetime.datetime.utcnow().isoformat() + "Z",
        "host":           os.uname().nodename,
        "python":         sys.version.split()[0],
        "file_count":     len(files_added),
        "total_bytes":    sum(f["bytes"] for f in files_added),
        "files_by_area":  _summarize_files(files_added),
        "notes": [
            "No secrets, tokens, or MCP client configs are included.",
            "Encryption is NOT applied. Store on encrypted volume or wrap yourself.",
        ],
    }


def _summarize_files(files_added: list) -> dict:
    out: dict = {}
    for f in files_added:
        head = f["path_in_zip"].split("/", 1)[0]
        rec = out.setdefault(head, {"count": 0, "bytes": 0})
        rec["count"] += 1
        rec["bytes"] += f["bytes"]
    return out


def _rotate(out_dir: Path, keep: int) -> list:
    removed = []
    if keep <= 0:
        return removed
    snaps = sorted(
        (p for p in out_dir.glob("teacher-snapshot-*.zip") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
    )
    excess = len(snaps) - keep
    for old in snaps[:max(0, excess)]:
        try:
            old.unlink()
            removed.append(str(old))
        except OSError:
            pass
    return removed


def main():
    start = time.time()
    out_dir = Path(os.environ.get("TEACHER_SNAPSHOT_DIR", str(HOME / "teacher-snapshots")))
    out_dir.mkdir(parents=True, exist_ok=True)
    keep = int(os.environ.get("TEACHER_SNAPSHOT_KEEP", "14"))

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_zip = out_dir / f"teacher-snapshot-{stamp}.zip"

    files_added = []
    missing_required = []
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for source in SOURCES:
            base = source["path"]
            if not base.exists():
                if source["required"]:
                    missing_required.append(str(base))
                continue
            count_before = len(files_added)
            for file_path, rel in iter_files(source):
                arcname = f"{source['arcname']}/{rel}"
                try:
                    zf.write(file_path, arcname=arcname)
                    files_added.append({
                        "path_in_zip": arcname,
                        "bytes":       file_path.stat().st_size,
                    })
                except OSError as e:
                    print(f"WARN  skipped {file_path}: {e}", file=sys.stderr)
            area_count = len(files_added) - count_before
            print(f"  + {source['arcname']:<18} {area_count:>5} files")

        manifest = build_manifest(files_added, start)
        if missing_required:
            manifest["missing_required"] = missing_required
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))

    rotated = _rotate(out_dir, keep)
    elapsed = time.time() - start

    result = {
        "ok":             len(missing_required) == 0,
        "path":           str(out_zip),
        "bytes":          out_zip.stat().st_size,
        "file_count":     len(files_added),
        "elapsed_seconds": round(elapsed, 2),
        "rotated_out":    rotated,
        "missing_required": missing_required,
    }
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()
