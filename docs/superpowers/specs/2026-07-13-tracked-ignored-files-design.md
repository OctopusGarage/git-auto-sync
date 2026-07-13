# Tracked Ignored Files Handling Design

## Goal

Make `git-auto-sync` handle provider-ignored files predictably when those files are
already tracked by Git. These files can keep the working tree dirty even after a
successful automated commit, which blocks `git pull --rebase` unless the tool
temporarily stashes them.

## Current Behavior

`sync_repo` asks the provider which changed paths to stage and which to ignore.
Ignored paths are left in the working tree. If `ai_gitignore_autowrite` is enabled,
the ignored path may be appended to `.gitignore`.

That is safe for untracked files, but it does not hide files that are already tracked.
Tracked ignored files still appear as modified in `git status`, so the next push flow
can see a dirty working tree after the tool commits the selected paths.

## Design

Use two layers of handling:

1. `git pull --rebase --autostash` is the default push behavior. This lets Git
   temporarily stash remaining local edits, rebase, then restore those edits.
2. Add a tracked-ignored policy for files that the provider ignored but Git already
   tracks.

The tracked-ignored policy has two modes:

- `leave_dirty` keeps the file modified in the working tree. This is the default and
  safest behavior. The tool reports these files as ignored, and autostash keeps sync
  from failing during pull/rebase.
- `skip_worktree` marks ignored tracked files with
  `git update-index --skip-worktree -- <path>`. This is opt-in. It is useful for
  local generated data or machine-specific files that should remain tracked upstream
  but stop participating in local auto-sync runs.

The tool will not automatically untrack files. Removing tracked files from the index
is a repository policy decision and can delete or stop publishing data unexpectedly.

## Configuration

Add a repo-level field:

```toml
tracked_ignored_policy = "leave_dirty"
```

Allowed values:

- `"leave_dirty"`: default.
- `"skip_worktree"`: opt-in local silencing for ignored tracked paths.

The field inherits from `[defaults]` the same way existing repo options do.

## Data Flow

1. Collect changes from `git status --porcelain -uall`.
2. Apply path policy and provider staging decision.
3. Stage and commit selected paths.
4. For provider-ignored paths, ask Git which are tracked.
5. If policy is `skip_worktree`, run `git update-index --skip-worktree -- <path>`
   for those tracked ignored paths.
6. If pushing, run `git pull --rebase --autostash`, then `git push`.

## Error Handling

- Invalid policy values fail config validation.
- `skip_worktree` failures fail the repo sync with a clear error before pull/push.
- Rebase conflicts still fail and abort the rebase, preserving the existing behavior.
- Autostash conflicts after rebase are reported by Git and surfaced as pull/rebase
  failures.

## Testing

Add tests for:

- Default `leave_dirty` can commit and push selected paths while preserving a tracked
  ignored local modification.
- `skip_worktree` marks tracked ignored paths and allows future sync runs to ignore
  them.
- Invalid config values are rejected.
- Existing add, commit, push, bare work-tree, and rebase conflict behavior remains
  unchanged.
