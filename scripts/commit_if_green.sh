#!/usr/bin/env bash
# commit_if_green.sh
#
# Run the project's standard check suite and, only if every check passes, stage
# changes, commit, and push — all in one invocation. Linux/Codespaces/CI companion
# to scripts/commit_if_green.ps1 (same check list, same flag semantics, same
# fail-fast / no-partial-commit guarantees).
#
# This script automates ONLY the mechanical "run checks, then commit+push"
# sequence (the same commands `just check` runs, invoked directly). It is NOT a
# substitute for the independent blueprint chapter-gate review required by
# .cursor/rules/mission-chapter-gate.mdc for any chartered DDE-N mission. This
# script exiting 0 means CI is green; it does NOT mean a blueprint chapter is
# done. See AGENTS.md, section "Mechanical commit helpers".
#
# Check list mirrors the justfile `check` recipe (lint typecheck test
# contract-test) exactly, in the same order:
#   1. uv run ruff check .
#   2. uv run ruff format --check .
#   3. uv run mypy
#   4. uv run pytest tests/unit tests/contract tests/recovery --cov --cov-report=term-missing
#   5. uv run python -m scripts.generate_contracts --check
#   6. uv run pytest tests/contract
#
# On the first failing check, the script stops immediately with a non-zero exit
# code and performs NO git operations at all (no add, no commit, no push).
#
# Never uses --no-verify, never skips hooks, never amends, never force-pushes,
# and never touches git config, per AGENTS.md's git safety rules.
#
# Usage:
#   commit_if_green.sh --message "commit message" [--push|--no-push] [--paths path1 path2 ...]
set -euo pipefail

MESSAGE=""
PUSH=1
PATHS=()

usage() {
  cat <<'EOF'
Usage: commit_if_green.sh --message "commit message" [--push|--no-push] [--paths path1 path2 ...]

  --message, -m   Commit message (required)
  --push          Push after commit (default)
  --no-push       Skip push after commit
  --paths         Specific paths to stage/commit (default: stage everything with `git add -A`)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message|-m)
      MESSAGE="${2:-}"
      shift 2
      ;;
    --push)
      PUSH=1
      shift
      ;;
    --no-push)
      PUSH=0
      shift
      ;;
    --paths)
      shift
      while [[ $# -gt 0 && "$1" != --* ]]; do
        PATHS+=("$1")
        shift
      done
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$MESSAGE" ]]; then
  echo "FAIL: --message is required" >&2
  usage
  exit 1
fi

step()  { echo "==> $*"; }
ok()    { echo "  OK: $*"; }
fail()  { echo "  FAIL: $*" >&2; }

run_check() {
  local name="$1"
  shift
  step "check: $name ($*)"
  if ! "$@"; then
    fail "$name failed"
    echo
    echo "SUMMARY: FAILED at check '$name'. No git operations were performed." >&2
    exit 1
  fi
  ok "$name"
}

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# Mirrors justfile `check: lint typecheck test contract-test` exactly — do not
# reorder or add/drop steps here without updating the justfile too.
run_check "lint (ruff check)" uv run ruff check .
run_check "lint (ruff format)" uv run ruff format --check .
run_check "typecheck (mypy)" uv run mypy
run_check "test (pytest)" uv run pytest tests/unit tests/contract tests/recovery --cov --cov-report=term-missing
run_check "contract-test (generate_contracts --check)" uv run python -m scripts.generate_contracts --check
run_check "contract-test (pytest tests/contract)" uv run pytest tests/contract

echo
echo "All checks passed."
echo

step "git add"
if [[ ${#PATHS[@]} -gt 0 ]]; then
  git add -- "${PATHS[@]}"
else
  git add -A
fi

nothing_staged=0
if [[ ${#PATHS[@]} -gt 0 ]]; then
  git diff --cached --quiet -- "${PATHS[@]}" && nothing_staged=1 || true
else
  git diff --cached --quiet && nothing_staged=1 || true
fi
if [[ "$nothing_staged" -eq 1 ]]; then
  fail "Nothing to commit (no staged changes after 'git add')."
  echo
  echo "SUMMARY: FAILED - nothing to commit. No commit was created." >&2
  exit 2
fi

step "git commit"
if [[ ${#PATHS[@]} -gt 0 ]]; then
  git commit -m "$MESSAGE" -- "${PATHS[@]}"
else
  git commit -m "$MESSAGE"
fi

commit_hash="$(git rev-parse --short HEAD)"
ok "committed $commit_hash"

if [[ "$PUSH" -ne 1 ]]; then
  echo
  echo "SUCCESS: checks passed, committed $commit_hash. Push skipped (--no-push)."
  exit 0
fi

step "git push"
branch="$(git rev-parse --abbrev-ref HEAD)"
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push
else
  echo "  No upstream configured for '$branch'; running 'git push -u origin HEAD'."
  git push -u origin HEAD
fi

echo
echo "SUCCESS: checks passed, committed and pushed $commit_hash."
exit 0
