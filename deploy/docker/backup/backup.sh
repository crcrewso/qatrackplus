#!/bin/bash
set -euo pipefail

BACKUP_DIR="/backups"
mkdir -p "$BACKUP_DIR" # If backup folder does not exist, create it.
DATE=$(date +%Y%m%d_%H%M%S)

# Tiered retention, matching qatrack_core's backup_site management command
# (used by the non-Docker Linux/Windows deployment path) so a deployer
# moving between them sees the same retention semantics. Every run keeps a
# "daily" backup; on top of that, if today is the configured weekly/monthly
# trigger day, a "weekly"/"monthly" copy is also kept, each aged out on its
# own schedule - so you keep a longer history without keeping every single
# daily backup forever.
DAYS_TO_KEEP="${BACKUP_DAYS_TO_KEEP:-7}"
WEEKS_TO_KEEP="${BACKUP_WEEKS_TO_KEEP:-5}"
MONTHS_TO_KEEP="${BACKUP_MONTHS_TO_KEEP:-12}"
# 0=Monday .. 6=Sunday, matching backup_site.py's Python convention (default
# 2 = Wednesday). `date +%u` is ISO weekday (1=Mon..7=Sun); subtract 1.
WEEKLY_DAY="${BACKUP_WEEKLY_DAY:-2}"
MONTHLY_DAY="${BACKUP_MONTHLY_DAY:-3}"
TODAY_WEEKDAY=$(( $(date +%-u) - 1 ))
TODAY_DAY_OF_MONTH=$(date +%-d)

echo "Starting backup at $DATE"

# Dump database once and tar media once; the same point-in-time snapshot is
# then copied into whichever retention tier(s) apply today, rather than
# re-dumping per tier.
export PGPASSWORD="${POSTGRES_PASSWORD:-}"
pg_dump -h postgres -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-qatrackplus}" -F c -f "$BACKUP_DIR/db_$DATE.tmp"
tar -czf "$BACKUP_DIR/media_$DATE.tmp" -C / media/

# Daily tier: always.
TIERS="daily"

# Weekly tier: only on the configured day of the week.
if [ "$TODAY_WEEKDAY" -eq "$WEEKLY_DAY" ]; then
    TIERS="$TIERS weekly"
fi

# Monthly tier: only on the configured day of the month.
if [ "$TODAY_DAY_OF_MONTH" -eq "$MONTHLY_DAY" ]; then
    TIERS="$TIERS monthly"
fi

for tier in $TIERS; do
    cp "$BACKUP_DIR/db_$DATE.tmp" "$BACKUP_DIR/db_${DATE}_${tier}.dump"
    cp "$BACKUP_DIR/media_$DATE.tmp" "$BACKUP_DIR/media_${DATE}_${tier}.tar.gz"
    echo "Kept $tier backup: db_${DATE}_${tier}.dump, media_${DATE}_${tier}.tar.gz"
done

rm -f "$BACKUP_DIR/db_$DATE.tmp" "$BACKUP_DIR/media_$DATE.tmp"

# Cleanup old backups, per tier, on that tier's own retention window.
find "$BACKUP_DIR" -type f -name "db_*_daily.dump" -mtime "+$DAYS_TO_KEEP" -delete
find "$BACKUP_DIR" -type f -name "media_*_daily.tar.gz" -mtime "+$DAYS_TO_KEEP" -delete
find "$BACKUP_DIR" -type f -name "db_*_weekly.dump" -mtime "+$((WEEKS_TO_KEEP * 7))" -delete
find "$BACKUP_DIR" -type f -name "media_*_weekly.tar.gz" -mtime "+$((WEEKS_TO_KEEP * 7))" -delete
find "$BACKUP_DIR" -type f -name "db_*_monthly.dump" -mtime "+$((MONTHS_TO_KEEP * 30))" -delete
find "$BACKUP_DIR" -type f -name "media_*_monthly.tar.gz" -mtime "+$((MONTHS_TO_KEEP * 30))" -delete

echo "Backup completed successfully"
