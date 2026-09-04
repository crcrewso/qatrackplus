# Release Checklist

> **Status: draft, not yet part of the Sphinx docs.** This checklist lives
> here as a root-level file for now rather than under `docs/developer/`.
> Until it's migrated, **the checklist should also be included (or linked)
> in the release announcement** for whichever release it's used on, so it
> doesn't get lost.
>
> **TODO (4.1 release):** move this content into the Sphinx documentation
> (`docs/developer/`, wired into the toctree in `docs/developer/guide.rst`)
> and remove this file, updating any links that pointed here.

## Documentation

- [ ] Re-review `AGENTS.md` for accuracy (repo layout, target branch name,
      supported language/database versions, workflow commands) — stale
      entries mislead both human contributors and AI agents.
- [ ] Re-review `CONTRIBUTING.md` for the same.
- [ ] Confirm `docs/release_notes.rst` has an entry for this release.
- [ ] Regenerate the database schema diagram (`make schema`) in
      `docs/developer/schema.rst` — it's currently showing the **v0.3.0**
      schema, over a decade stale. **Note:** before just regenerating it
      again, revisit whether a single static generated image is even the
      right way to present the schema to developers going forward — it's
      gone unmaintained for many major versions despite the tooling
      existing, which suggests the format itself isn't meeting the need.
- [ ] Review every command in every `.rst` doc for copy-button correctness.
      `docs/conf.py` configures `sphinx_copybutton` with
      `copybutton_prompt_text = ">>  "` so PowerShell-style `>>` prompts get
      stripped on copy — that depends on every prompted block using that
      exact prefix consistently. Check for mixed prompt styles, multi-line
      commands, and stray comment lines that might copy along with the
      command or get incorrectly stripped.

## Localization

- [ ] Regenerate compiled catalogs: `uv run python manage.py compilemessages`.
- [ ] For each language directory under `qatrack/locale/` (currently `fr`,
      `fr-ca`, `es`), diff the `.po` file against the English source strings
      and identify missing or untranslated (empty/fuzzy `msgstr`) entries.
- [ ] Confirm every language directory has a compiled `.mo` file (`fr_CA` is
      currently missing one — see the "note for AI agents" on `locale/` in
      `AGENTS.md`).

## Packaging

- [ ] Regenerate `requirements/win-mssql.txt` (the pip fallback for
      production Windows/MS SQL Server installs that can't set up `uv`):
      `uv export --format requirements-txt --extra win --extra mssql --no-dev -o requirements/win-mssql.txt`.

## Versioning

- [ ] Bump `version` in `pyproject.toml`.
- [ ] Bump `VERSION` in `Makefile` — this currently drifts out of sync with
      `pyproject.toml` (e.g. `3.1.0` vs `4.0.0` as of this writing).

## Testing

- [ ] Full test suite passes: `uv run pytest`.
- [ ] Migrations check clean: `uv run python manage.py makemigrations --check`.
