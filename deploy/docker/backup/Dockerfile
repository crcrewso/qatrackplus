FROM alpine:3.19

ARG HOST_UID=999
ARG HOST_GID=999

# Pinned to match the `postgres` service's postgres:15-alpine image exactly.
# The floating `postgresql-client` meta-package resolves to whatever Alpine
# currently packages (16.x as of writing) - a newer major version than the
# server, whose pg_restore then can't read this client's pg_dump archives
# (custom-format dumps embed a version tag; older pg_restore rejects newer
# ones). Bump this alongside the `postgres` service's image tag, together.
RUN apk add --no-cache postgresql15-client bash tar dcron dos2unix procps

COPY backup.sh /backup.sh
RUN dos2unix /backup.sh && chmod +x /backup.sh

# Create volume mount point with matching UID/GID from Django
RUN mkdir -p /media && chown -R ${HOST_UID}:${HOST_GID} /media

# Setup cron job (runs daily at 2 AM)
RUN echo "0 2 * * * bash /backup.sh >> /var/log/backup.log 2>&1" > /etc/crontabs/root

CMD ["crond", "-f", "-d", "8"]
