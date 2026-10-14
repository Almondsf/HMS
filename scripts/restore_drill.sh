#!/usr/bin/env bash
# Prove a backup restores: load it into an EMPTY scratch database and
# compare the result with the report saved at backup time.
#
#   RESTORE_DATABASE_URL=postgres://.../hms_restore_drill scripts/restore_drill.sh backups/hms-....dump
#
# Never point RESTORE_DATABASE_URL at a real database: the script refuses
# to restore into one that already has tables.
set -euo pipefail

dump="${1:?Usage: scripts/restore_drill.sh <backup.dump>}"
: "${RESTORE_DATABASE_URL:?Set RESTORE_DATABASE_URL to an empty scratch database}"

echo "Checking the backup file..."
if [ -f "$dump.sha256" ]; then
  (cd "$(dirname "$dump")" && sha256sum --check --quiet "$(basename "$dump").sha256")
  echo "  checksum OK"
fi

tables=$(psql "$RESTORE_DATABASE_URL" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema')")
if [ "$tables" != "0" ]; then
  echo "Refusing: the target database is not empty ($tables tables). Use a fresh scratch database." >&2
  exit 1
fi

echo "Restoring..."
start=$(date +%s)
pg_restore --no-owner --no-privileges --exit-on-error --dbname="$RESTORE_DATABASE_URL" "$dump"
echo "  restored in $(( $(date +%s) - start ))s"

echo "Comparing with the report taken at backup time..."
restored_report="$(mktemp)"
DATABASE_URL="$RESTORE_DATABASE_URL" python manage.py database_report > "$restored_report"
if diff -u "$dump.report.json" "$restored_report"; then
  echo "RESTORE VERIFIED: every schema, table count, migration and the audit-log protection match."
else
  echo "DIFFERENCES FOUND (above). Small increases are expected only if the database was busy during the backup." >&2
  exit 1
fi
