#!/usr/bin/env bash
# Back up the whole database (platform + every hospital schema).
#
#   DATABASE_URL=postgres://... scripts/backup.sh [output-dir]
#
# Writes <dir>/hms-<UTC time>.dump (pg_dump custom format), a .sha256
# checksum, and .report.json (python manage.py database_report) for
# verifying restores. Backups contain patient data: store them encrypted
# and access-controlled, never in git or chat.
set -euo pipefail

: "${DATABASE_URL:?Set DATABASE_URL to the database to back up}"
out_dir="${1:-backups}"
mkdir -p "$out_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
file="$out_dir/hms-$stamp.dump"

echo "Recording what the database contains..."
python manage.py database_report > "$file.report.json"

echo "Dumping..."
pg_dump --format=custom --no-owner --no-privileges --file="$file" "$DATABASE_URL"

# A dump that can't be listed can't be restored
pg_restore --list "$file" > /dev/null
(cd "$out_dir" && sha256sum "$(basename "$file")" > "$(basename "$file").sha256")

echo "Backup written: $file ($(du -h "$file" | cut -f1))"
echo "Report:         $file.report.json"
