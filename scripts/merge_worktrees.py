#!/usr/bin/env python3
"""
merge_worktrees.py — Merge parallel Copilot worktrees into main.

Was es tut:
  1. Alle git worktrees auflisten (ohne main)
  2. Neue Story-Dateien aus jedem Worktree nach main kopieren
  3. sprint-status.yaml aus allen Worktrees zusammenführen
     (pro Key den am weitesten fortgeschrittenen Status übernehmen)
  4. Optional: git add + commit

Aufruf:
  python scripts/merge_worktrees.py [--commit] [--dry-run]
"""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Status-Priorität (höher = weiter fortgeschritten) ──────────────────────
STATUS_PRIORITY = {
    "backlog": 0,
    "ready-for-dev": 1,
    "in-progress": 2,
    "review": 3,
    "done": 4,
    "optional": 0,  # retrospective-Marker, bleibt unverändert
}

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = REPO_ROOT / "_bmad-output" / "implementation-artifacts"
SPRINT_STATUS_FILE = ARTIFACTS_DIR / "sprint-status.yaml"


# ── Git helpers ─────────────────────────────────────────────────────────────

def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def list_worktrees() -> list[dict]:
    """Return list of {path, branch} for all non-main worktrees."""
    output = git("worktree", "list", "--porcelain")
    worktrees = []
    current: dict = {}
    for line in output.splitlines():
        if line.startswith("worktree "):
            current = {"path": Path(line[len("worktree "):].strip())}
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):].strip()
        elif line == "" and current:
            if current.get("path") != REPO_ROOT:
                worktrees.append(current)
            current = {}
    if current and current.get("path") != REPO_ROOT:
        worktrees.append(current)
    return worktrees


# ── Sprint-status parser ─────────────────────────────────────────────────────

def parse_status_block(yaml_path: Path) -> dict[str, str]:
    """Extract {key: status} from development_status block."""
    statuses: dict[str, str] = {}
    in_block = False
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "development_status:":
            in_block = True
            continue
        if in_block:
            # end of block on next top-level key (no leading spaces)
            if line and not line.startswith(" ") and not line.startswith("#"):
                break
            m = re.match(r"^\s{2}([\w\-]+):\s+(\S+)", line)
            if m:
                statuses[m.group(1)] = m.group(2)
    return statuses


def merge_statuses(base: dict[str, str], *others: dict[str, str]) -> dict[str, str]:
    """For each key take the highest-priority status across all sources."""
    merged = dict(base)
    for other in others:
        for key, status in other.items():
            if key not in merged:
                merged[key] = status
            else:
                p_existing = STATUS_PRIORITY.get(merged[key], 0)
                p_new = STATUS_PRIORITY.get(status, 0)
                if p_new > p_existing:
                    merged[key] = status
    return merged


def apply_merged_statuses(yaml_path: Path, merged: dict[str, str], dry_run: bool) -> None:
    """Rewrite development_status block and bump last_updated."""
    content = yaml_path.read_text(encoding="utf-8")

    # Bump last_updated
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    content = re.sub(
        r'^(last_updated:\s+")[^"]+(")',
        rf'\g<1>{now}\g<2>',
        content,
        flags=re.MULTILINE,
    )

    # Replace each status value in development_status block
    def replace_status(m: re.Match) -> str:
        key = m.group(1)
        if key in merged:
            return f"  {key}: {merged[key]}"
        return m.group(0)

    content = re.sub(r"^  ([\w\-]+): \S+", replace_status, content, flags=re.MULTILINE)

    if dry_run:
        print(f"\n[dry-run] Would write to {yaml_path}:")
        for key, val in sorted(merged.items()):
            print(f"  {key}: {val}")
    else:
        yaml_path.write_text(content, encoding="utf-8")
        print(f"  ✓ {yaml_path.relative_to(REPO_ROOT)} updated")


# ── Story file collector ────────────────────────────────────────────────────

def collect_new_story_files(worktree_path: Path) -> list[Path]:
    """Return story .md files in worktree that don't exist in main yet."""
    wt_artifacts = worktree_path / "_bmad-output" / "implementation-artifacts"
    if not wt_artifacts.exists():
        return []
    new_files = []
    for f in wt_artifacts.glob("*.md"):
        if not (ARTIFACTS_DIR / f.name).exists():
            new_files.append(f)
    return new_files


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="git add + commit after merge")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen, don't write")
    args = parser.parse_args()

    worktrees = list_worktrees()
    if not worktrees:
        print("No worktrees found (other than main). Nothing to merge.")
        sys.exit(0)

    print(f"Found {len(worktrees)} worktree(s):")
    for wt in worktrees:
        print(f"  {wt['path'].name}  [{wt.get('branch', 'detached')}]")

    # 1. Collect story files
    copied: list[Path] = []
    print("\n── Story files ─────────────────────────────────────────────────")
    for wt in worktrees:
        new_files = collect_new_story_files(wt["path"])
        for src in new_files:
            dest = ARTIFACTS_DIR / src.name
            if args.dry_run:
                print(f"  [dry-run] Would copy {src.name}")
            else:
                shutil.copy2(src, dest)
                print(f"  ✓ Copied {src.name}")
                copied.append(dest)

    if not copied and not args.dry_run:
        print("  (no new story files)")

    # 2. Merge sprint-status.yaml
    print("\n── sprint-status.yaml ──────────────────────────────────────────")
    base_statuses = parse_status_block(SPRINT_STATUS_FILE)
    all_statuses = [base_statuses]

    for wt in worktrees:
        wt_status = wt["path"] / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"
        if wt_status.exists():
            wt_parsed = parse_status_block(wt_status)
            all_statuses.append(wt_parsed)
            print(f"  Parsed {wt['path'].name}:")
            for k, v in wt_parsed.items():
                if v != base_statuses.get(k):
                    print(f"    {k}: {base_statuses.get(k, '—')} → {v}")

    merged = merge_statuses(*all_statuses)
    apply_merged_statuses(SPRINT_STATUS_FILE, merged, dry_run=args.dry_run)

    # 3. Optional commit
    if args.commit and not args.dry_run:
        print("\n── Git commit ──────────────────────────────────────────────────")
        try:
            git("add", str(ARTIFACTS_DIR))
            story_names = ", ".join(f.stem for f in copied) if copied else "sprint-status only"
            git("commit", "-m", f"Merge worktrees: {story_names}")
            print(f"  ✓ Committed")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Commit failed: {e.stderr}")
            sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
