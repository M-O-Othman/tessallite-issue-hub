# Tessallite Issue Hub — Future Features and Enhancements

Out-of-scope items identified during implementation. Do not implement without explicit instruction.

## 1. Concurrency-Safe Index Migrations

Alembic's `op.create_index` emits plain `CREATE INDEX`, which takes a `SHARE` lock and blocks writes for the duration of the build. On a large `issues` table this is a write outage during deploy.

Make index-creating migrations use `CREATE INDEX CONCURRENTLY` inside `op.get_context().autocommit_block()`, since `CONCURRENTLY` cannot run in a transaction. This requires handling the failure mode `CONCURRENTLY` introduces: a failed build leaves an `INVALID` index behind that must be detected via `pg_index.indisvalid` and dropped before retry.

Affects: `migrations/versions/f1127bbc1194_add_performance_indexes.py` (already applied to production out-of-band; the change would only benefit environments provisioned from scratch).

## 2. Trigram Index for `aka` and Free-Text Search

`search.py` filters `aka` with a `~*` regex and a leading-wildcard `ILIKE '%q%'`, and applies the same wide `ILIKE` pattern across `title`, `description`, and other text columns. No B-Tree can serve these patterns, so all such searches are sequential scans.

A GIN trigram index (`CREATE EXTENSION pg_trgm; CREATE INDEX ... USING gin (aka gin_trgm_ops)`) would serve both operators and has no row-size limit, making it immune to the oversized-value problem in `Docs/known_issues.md` item A1. `pg_trgm` is available on the production server but not installed.

Deferred by explicit decision during the production index rollout; the plain `aka` index was dropped instead.

## 3. `aka` Data Repair Backfill

See `Docs/known_issues.md` Active item A1. Requires a parser fix in `registry_parser.py` plus a one-off backfill truncating affected `aka` values to their leading identifier.
