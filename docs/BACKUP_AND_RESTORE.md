# Backups and restores

A backup only counts once it has been restored. This is the procedure, and
the drill that proves it works.

**Tested:** 14 Oct 2026 on a local copy (2 schemas, 68 visits, 2,377 audit
events). Backup 368 KB; restore 9 s; every table count, migration and the
audit log's append-only protection verified identical.

## What protects the data

| Layer | What it covers | Notes |
|---|---|---|
| **Render managed backups** | Whole database, automatic | Paid Postgres plans only. Check *Dashboard → your database → Recovery* for what your plan keeps. **Free databases have no backups and expire.** |
| **Manual backups** (`scripts/backup.sh`) | Whole database, on demand | Before every risky change: upgrades, `adopt_legacy_data`, bulk imports. |
| **Monthly restore drill** (`scripts/restore_drill.sh`) | Proves the above actually restore | Takes ~10 minutes. |

Every backup holds **patient data**. Keep backup files encrypted and
access-controlled, never in git, email or chat, and delete them according
to your retention policy (agree one with each hospital; the NDPA expects
it).

## Requirements

Run the scripts **from your own computer** (the server image has no
`pg_dump`):

- PostgreSQL client tools **at least as new as the server** (`pg_dump --version`).
  On Windows they are in `C:\Program Files\PostgreSQL\<version>\bin`; add
  that folder to `PATH`.
- This repository with its virtual environment activated (the scripts run
  `python manage.py database_report`).
- The database's **External Database URL** (Render: database → Connect →
  External). Treat it like a password.

Use Git Bash (Windows) or any shell (macOS/Linux).

## Take a backup

```bash
export DATABASE_URL='postgresql://...external url...'
scripts/backup.sh backups
```

This writes three files to `backups/`:
- `hms-<time>.dump`: the backup itself
- `.sha256`: a checksum
- `.report.json`: what the database contained at the time

The script confirms the dump is readable before reporting success.

## Monthly restore drill

Restores into a **scratch** database and compares with the report taken at
backup time. It refuses to restore into a database that already has tables,
so it cannot overwrite real data.

```bash
# 1. A fresh, empty scratch database (locally, or a temporary Render database)
psql "$ADMIN_URL" -c "CREATE DATABASE hms_restore_drill"

# 2. Restore and verify
RESTORE_DATABASE_URL='postgresql://.../hms_restore_drill' scripts/restore_drill.sh backups/hms-<time>.dump

# 3. Clean up
psql "$ADMIN_URL" -c "DROP DATABASE hms_restore_drill"
```

`RESTORE VERIFIED` means every schema, table count, migration and the audit
protection matched. Record the date, the backup size and the restore time in
the log below.

If the live database was busy during the backup, a few extra rows (usually
audit events) can appear in the comparison. Back up during a quiet period to
get an exact match.

## Restoring for real (data loss or corruption)

Never restore over the live database: restore alongside it, check, then
switch.

1. **Choose the restore point:** Render's recovery (dashboard) or your
   latest good `.dump`.
2. **Restore into a new database**:
   - **Render recovery:** use Render's restore option, which creates a new instance.
   - **From a dump:** create a new Render Postgres, then run
     `RESTORE_DATABASE_URL=<its external URL> scripts/restore_drill.sh <dump>`.
3. **Check it:** `DATABASE_URL=<new external url> python manage.py database_report`.
   Then sign in to one hospital against it if you can.
4. **Switch:** set the service's `DATABASE_URL` to the new database's
   *internal* URL and redeploy. Pre-deploy migrations bring it up to date.
5. **Tell the affected hospitals** what period was lost (between the backup
   and the incident), so they can re-enter it from paper. Keep the old
   database untouched until the investigation is finished.

## Drill log

| Date | Backup | Size | Restore time | Result | By |
|---|---|---|---|---|---|
| 2026-10-14 | local demo database | 368 KB | 9 s | Verified | setup |
