#!/usr/bin/env bash
#
# Camelot Bare-Metal Datastore Setup (Phase 1)
# No Docker. Direct native installations optimized for 8GB Host constraint.
#

set -euo pipefail

echo "=> [1/4] Configuring PostgreSQL (Relational state & receipts)"
# sudo apt-get install -y postgresql postgresql-contrib
# Edit /etc/postgresql/*/main/postgresql.conf:
# - shared_buffers = 1GB (tuned for 8GB host limit alongside Neo4j)
# - max_connections = 200

echo "=> [2/4] Configuring Redis (PubSub & Cache)"
# sudo apt-get install -y redis-server
# Edit /etc/redis/redis.conf:
# - maxmemory 256mb
# - maxmemory-policy allkeys-lru

echo "=> [3/4] Configuring Neo4j (Canonical Graph Memory)"
# wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
# echo 'deb https://debian.neo4j.com stable latest' | sudo tee -a /etc/apt/sources.list.d/neo4j.list
# sudo apt-get update && sudo apt-get install -y neo4j
# Edit /etc/neo4j/neo4j.conf:
# - server.memory.heap.initial_size=1G
# - server.memory.heap.max_size=1G
# - server.memory.pagecache.size=1G

echo "=> [4/4] Configuring MinIO (Object Storage for VFS & Raw Crawls)"
# wget https://dl.min.io/server/minio/release/linux-amd64/minio
# chmod +x minio && sudo mv minio /usr/local/bin/
# systemd service: ExecStart=/usr/local/bin/minio server /opt/camelot/data/minio

echo "=> Datastore provisioning scripts generated. Review memory bounds before starting."
