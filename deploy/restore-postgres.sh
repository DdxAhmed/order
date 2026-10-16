#!/usr/bin/env sh
set -eu

# Use only on a disposable test database first. This replaces the target database contents.
: "${1:?Pass the backup .sql.gz file as the first argument}"
backup_file="$1"
test -f "$backup_file"
test -f "$backup_file.sha256"
(cd "$(dirname "$backup_file")" && sha256sum -c "$(basename "$backup_file").sha256")
gunzip -c "$backup_file" | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
echo "Restore completed. Verify application readiness and a non-sensitive record count."
