# tech-demos

A weekday playground. One new library or tool from X bookmarks becomes a small single-user MVP demo, shipped as its own pull request. Never create a new repository for a demo.

## Layout

```
apps/<kebab-slug>/          one self-contained demo
skills/project-planning/    planning skill agents follow before coding
tracking/seen-bookmarks.json
```

`apps/` holds one app per demo. Nothing is shared between apps.

## Run an app

```bash
cd apps/<slug> && bun install && bun run dev
```

## Bookmark tracking

`tracking/seen-bookmarks.json` has four arrays: `proposed`, `approved`, `skipped`, and `built`.

Each entry has this shape:

```json
{ "id": "", "title": "", "url": "", "date": "" }
```

| Field | Meaning |
| --- | --- |
| `id` | Bookmark or post id |
| `title` | Short name of the library or tool |
| `url` | Source link |
| `date` | Date recorded (`YYYY-MM-DD`) |
