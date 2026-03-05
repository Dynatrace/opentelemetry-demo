#!/bin/bash
set -e

echo "shared_preload_libraries = 'pg_stat_statements'" >> "/var/lib/postgresql/data/postgresql.conf"
echo "track_activity_query_size = 4096" >> "/var/lib/postgresql/data/postgresql.conf"
