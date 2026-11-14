# Agent rules

This repo is a sticky monorepo for small daily tech demos. One app per demo lives under `apps/<kebab-slug>/`. Never create a new repository. One pull request per demo.

## Scope

Only add or modify files inside `apps/<slug>/` for a demo (plus `tracking/seen-bookmarks.json` when told). Never touch other apps.

## Plan before coding

Before coding, plan with `skills/project-planning/SKILL.md` and write `apps/<slug>/PLAN.md`:

- goal
- single-user MVP + outs
- vertical-slice tasks
- stack with rationale
- deferred items

## Runtime and scaffold

Bun is the runtime and package manager. Each app is self-contained with its own `package.json` and a `bunfig.toml` containing:

```toml
[install]
minimumReleaseAge = 259200
```

Create that `bunfig.toml` before any install. Start from an official `bunx create-*` scaffold. Use the shadcn/ui minimalist preset for UI.

## App README

Each app needs a short `apps/<slug>/README.md` covering what it demos, the source link, and how to run it.

## Demo pull requests

Every demo PR MUST include at least one screenshot AND at least one video (screen recording) of the running app, embedded or attached in the PR description. Not optional.

One PR per demo.
