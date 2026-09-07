# Database Design: Camelot-VPS Hub

## 1. PostgreSQL Schema

```sql
-- Tenants
CREATE TABLE tenants (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workspaces
CREATE TABLE workspaces (
  id UUID PRIMARY KEY,
  tenant_id UUID REFERENCES tenants(id),
  name TEXT NOT NULL,
  timezone TEXT
);

-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL
);

-- Memberships
CREATE TABLE memberships (
  user_id UUID REFERENCES users(id),
  tenant_id UUID REFERENCES tenants(id),
  workspace_id UUID REFERENCES workspaces(id),
  role TEXT NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (user_id, tenant_id, workspace_id)
);

-- Missions
CREATE TABLE missions (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  workspace_id UUID NOT NULL,
  objective TEXT NOT NULL,
  risk_tier TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Receipts
CREATE TABLE receipts (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  type TEXT NOT NULL,
  actor TEXT NOT NULL,
  action_ref TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  receipt_hash TEXT NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Row-Level Security
ALTER TABLE missions ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipts ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_missions ON missions
  USING (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_receipts ON receipts
  USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

## 2. Neo4j Schema

See prior Cypher constraints and indexes (organization_id_unique, tenant_id_unique, etc.).

## 3. Qdrant Collection

`camelot_context_v1`, 1024-dim cosine, payload indexes on `tenant_id`, `workspace_id`, `status`, `classification`.
