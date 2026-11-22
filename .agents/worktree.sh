#!/usr/bin/env bash
# Personal feature-worktree workflow. See .agents/worktrees.md.
#   worktree.sh new <name>   create or reuse .worktrees/<name> on branch feat/<name>
#   worktree.sh ship <name>  rebase onto dev, run checks, push to origin/dev, clean up
#   worktree.sh clean        remove feat/* worktrees whose commits are all in origin/dev
# Exit codes: 0 ok, 1 usage/dirty, 2 rebase conflict, 3 checks failed, 4 push kept failing.
set -euo pipefail

main_root="$(cd "$(git rev-parse --path-format=absolute --git-common-dir)/.." && pwd)"
cd "$main_root"

cmd="${1:-}"; name="${2:-}"
[[ -n "$cmd" && ( -n "$name" || "$cmd" == clean ) ]] || { echo "usage: $0 new|ship <name> | clean" >&2; exit 1; }
branch="feat/$name"
dir="$main_root/.worktrees/$name"

base_ref() {
  if git ls-remote --exit-code --heads origin dev >/dev/null; then echo origin/dev; else echo origin/main; fi
}

# Keep the main checkout on dev and fast-forwarded to origin/dev. Never discards local work.
sync_main() {
  local b
  b="$(git -C "$main_root" symbolic-ref --short -q HEAD || true)"
  if [[ "$b" != dev ]]; then
    if [[ -z "$(git -C "$main_root" status --porcelain --untracked-files=no)" ]]; then
      git -C "$main_root" switch -q dev 2>/dev/null || git -C "$main_root" switch -q -c dev --track origin/dev
    else
      echo "main checkout is on '$b' with local changes; not switched to dev" >&2; return 0
    fi
  fi
  if [[ -n "$(git -C "$main_root" status --porcelain --untracked-files=no)" ]]; then
    echo "main checkout has local changes; dev not updated" >&2; return 0
  fi
  git -C "$main_root" merge -q --ff-only origin/dev 2>/dev/null \
    && echo "main checkout: dev at $(git -C "$main_root" rev-parse --short HEAD)" \
    || echo "main checkout dev has diverged from origin/dev; not updated" >&2
}

case "$cmd" in
  new)
    git fetch -q origin
    if [[ -d "$dir" ]]; then
      echo "reusing $dir"
    elif git show-ref -q --verify "refs/heads/$branch"; then
      git worktree add -q "$dir" "$branch"
    else
      git worktree add -q -b "$branch" "$dir" "$(base_ref)"
    fi
    # The gitignored .env holds local DB credentials; worktrees need it for check.sh's backend tests.
    [[ -f "$main_root/.env" && ! -e "$dir/.env" ]] && ln -s "$main_root/.env" "$dir/.env"
    git ls-remote --exit-code --heads origin dev >/dev/null && sync_main >&2
    echo "$dir"
    ;;

  ship)
    [[ -d "$dir" ]] || { echo "no worktree at $dir" >&2; exit 1; }
    cd "$dir"
    [[ -z "$(git status --porcelain)" ]] || { echo "uncommitted changes in $dir; commit first" >&2; exit 1; }

    for attempt in 1 2 3; do
      git fetch -q origin
      base="$(base_ref)"
      if ! git rebase -q "$base"; then
        git rebase --abort
        echo "CONFLICT rebasing $branch onto $base; worktree kept at $dir" >&2
        exit 2
      fi
      ./scripts/check.sh || { echo "checks failed; worktree kept at $dir" >&2; exit 3; }
      # Non-force push: git rejects it if dev moved since the fetch, so we rebase and retry.
      if git push -q origin "HEAD:refs/heads/dev"; then
        cd "$main_root"
        git worktree remove --force "$dir"
        git branch -q -D "$branch"
        echo "shipped $branch to origin/dev"
        sync_main
        exit 0
      fi
      echo "origin/dev moved, retrying ($attempt/3)" >&2
    done
    echo "push to origin/dev kept failing; worktree kept at $dir" >&2
    exit 4
    ;;

  clean)
    # Remove feat/* worktrees and branches whose every commit already landed in origin/dev.
    # Keeps anything with unshipped commits, uncommitted changes, or no commits yet (it may be
    # another agent's fresh worktree). Safe to rerun.
    git fetch -q --prune origin
    git worktree prune
    base="$(base_ref)"
    for ref in $(git for-each-ref --format='%(refname:short)' 'refs/heads/feat/'); do
      n="${ref#feat/}"; d="$main_root/.worktrees/$n"
      ahead="$(git rev-list --count "$base..$ref")"
      unshipped="$(git cherry "$base" "$ref" | grep -c '^+' || true)"
      dirty=""
      [[ -d "$d" && -n "$(git -C "$d" status --porcelain)" ]] && dirty=1
      if [[ -n "$dirty" ]]; then
        echo "kept $n: uncommitted changes"
      elif [[ "$ahead" -eq 0 ]]; then
        echo "kept $n: no commits yet"
      elif [[ "$unshipped" -gt 0 ]]; then
        echo "kept $n: $unshipped unshipped commit(s)"
      else
        [[ -d "$d" ]] && git worktree remove --force "$d"
        git branch -q -D "$ref"
        echo "removed $n: already in $base"
      fi
    done
    for d in "$main_root"/.worktrees/*/; do
      [[ -d "$d" ]] || continue
      git worktree list --porcelain | grep -qx "worktree ${d%/}" \
        || echo "stray folder ${d%/}: not a registered worktree; check it and delete by hand" >&2
    done
    git ls-remote --exit-code --heads origin dev >/dev/null && sync_main
    ;;

  *) echo "usage: $0 new|ship|clean <name>" >&2; exit 1 ;;
esac
