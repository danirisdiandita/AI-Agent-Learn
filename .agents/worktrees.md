# Feature worktrees (personal workflow)

Every feature, fix, or change you add goes in its own git worktree, never in the main checkout. When it's done and merges cleanly, it ships to `origin/dev` automatically.

The script `.agents/worktree.sh` does every step. Use it instead of running the git commands by hand. It lives in the main checkout and is not copied into worktrees, so call it by this path:

```bash
ROOT="$(cd "$(git rev-parse --path-format=absolute --git-common-dir)/.." && pwd)"
"$ROOT/.agents/worktree.sh" new <name>    # prints the worktree path
"$ROOT/.agents/worktree.sh" ship <name>
"$ROOT/.agents/worktree.sh" clean
```

## The main checkout tracks dev

The main checkout, the repository folder outside `.worktrees/`, always stays on `dev` and up to date with `origin/dev`. Never commit or edit files there. `worktree.sh` keeps it in sync after every `new` and every successful `ship`. If the main checkout has uncommitted changes to tracked files, the script leaves it alone and prints a warning. Tell the user when that happens.

## Steps

1. Pick a short kebab-case `<name>` for the feature, such as `agent-runtime-api`.
2. Run `worktree.sh new <name>`. It creates `.worktrees/<name>` on branch `feat/<name>`, based on `origin/dev` (or `origin/main` while `dev` doesn't exist). Rerunning it reuses the existing worktree.
3. Do all edits, installs, and commands inside that path. Never edit files in the main checkout.
4. Commit your work in small commits on `feat/<name>`.
5. Run `worktree.sh ship <name>`. It rebases onto the latest `origin/dev`, runs `scripts/check.sh`, pushes to `origin/dev` without force, then removes the worktree and branch.
6. Clean up, as described below.

## When ship stops

The script never force-pushes and never resolves conflicts on its own. Report the exit code to the user and stop:

| Exit | Meaning | What to do |
| --- | --- | --- |
| 1 | Uncommitted changes, or no such worktree | Commit, then ship again |
| 2 | Rebase conflict with `dev` | Tell the user which files conflict. Do not push. Worktree is kept |
| 3 | `scripts/check.sh` failed | Fix inside the worktree, commit, ship again |
| 4 | `dev` kept moving during 3 push attempts | Ship again later |

Several agents can each have their own worktree at once. Pushes to `dev` can't overwrite each other, because git rejects any push that isn't a fast-forward and the script then rebases and retries.

## Clean up after every task

Before you report a task as done, whether it shipped or stopped, leave nothing running and nothing stale behind.

1. Stop every process you started: dev servers (`moon run :dev`, `runserver`, `vite`), watchers, and background shells. Stop them by the task ID or PID you got when you started them. Never use `pkill -f` or `killall` with a pattern, because that can kill another agent's servers or the user's.
2. Delete temporary files you made outside the worktree, such as test repos and logs in the scratchpad. Files inside the worktree go away with it.
3. Run `worktree.sh clean`. It prunes stale worktree records, then checks each local `feat/*` branch:

   | State | What clean does |
   | --- | --- |
   | Has commits, and every one is already in `origin/dev` | Removes the worktree and deletes the branch |
   | Has commits not in `origin/dev` yet | Keeps it and prints how many |
   | Has uncommitted changes | Keeps it |
   | Has no commits yet | Keeps it, because it may be another agent's new worktree |

   It also prints a warning for any folder in `.worktrees/` that isn't a registered worktree, and fast-forwards the main checkout. It never deletes unshipped work and is safe to rerun. Branches outside `feat/` are not touched.
4. Pass on every `kept` and `stray folder` line to the user. Don't delete them yourself; the user decides.

Run `clean` at the start of a session too, so leftovers from earlier sessions get noticed.
