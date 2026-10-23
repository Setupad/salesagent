# Setupad VPS migration reconciliation, 2026-10-23

## Cause

The VPS records `f7d2c3b4a901`. Commit `b0e267d0` defined that merge with
parents `e6bb3ee6ae13` and `ec376a1c7624`. The replacement in `294a107f`
(rebased as `e0affa05`) retained only `ec376a1c7624`. The deployed schema
retained the webhook branch's `protocol` column, but the replacement graph
no longer records that branch as applied.

The shipped migration files remain unchanged. The deployment merge revision
`526ce4501041` joins upstream `7f31c0ab94d2` and VPS `f7d2c3b4a901`.

## Reconciliation Proof

[The operator SQL](setupad-vps-reconcile-20261023.sql) locks the version and
webhook tables, checks the exact starting revision, and verifies both skipped
migrations' complete effects:

- `a1f4c7d92b30` only normalizes `authentication_type` in
  `push_notification_configs`. An empty table proves that no updates remain.
- `6a52cf43ad75` only adds nullable `protocol VARCHAR(20)` without a default.
  The SQL requires that exact column definition.

Only after those checks does the SQL insert `6a52cf43ad75` as a second
version row. It preserves `f7d2c3b4a901`. Alembic then executes the merge
`e6bb3ee6ae13` and every remaining upstream migration normally.

Do not replace this with `alembic stamp`: the earlier stamp attempt removed
the VPS marker and caused Alembic to repeat `1497aa06013c`, although its
`media_buys.revision` column and descendants already belong to the VPS lineage.

## Rehearsal Evidence

A fresh custom-format production dump was restored into
`salesagent_reconcile_20261023`, with objects owned by `salesagent`.
No application processes or schedulers ran against that copy.

1. An ordinary `upgrade head` reproduced the duplicate `protocol` error.
2. Transaction rollback left the single starting revision `f7d2c3b4a901`.
3. The guarded SQL completed, preserving the VPS marker.
4. An ordinary `upgrade head` completed at `526ce4501041`.
5. Row counts remained: tenants 8, principals 12, media buys 30, creatives 23,
   accounts 8. All 12 principal token hashes matched SHA-256 of the original
   tokens. Both tenant host columns were populated.

The upstream account repair migrated one malformed brand ID, as intended.

## Production Procedure

Build the immutable deployment image while the old application runs. Capture
its runtime options and a private database backup. Stop the application before
the final backup and reconciliation: the upstream migrations remove columns
the old image uses. Apply the SQL with `psql -v ON_ERROR_STOP=1`, then run
the image's ordinary Alembic upgrade without starting application schedulers.
Start the image with the captured runtime configuration and verify health and
read-only tenant endpoints.

If migration or rollout fails, keep the application stopped. Restore the
post-stop database backup before restarting the rollback image. Never run
the old image against the upgraded schema or restore a stale backup over
accepted buyer writes.