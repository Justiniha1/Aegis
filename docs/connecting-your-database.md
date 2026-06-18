# Connecting Your Database to Comet

Comet runs read-only checks against your database and reports only results/metrics to the
dashboard (see `data-residency.md`). To connect it safely, create a **dedicated, read-only,
least-privilege service account** scoped to only what the checks need. This is the same model
Monte Carlo and Bigeye use, and it's what makes a security review straightforward.

Principles:
- **Dedicated service user** — never a shared or human login (easy to audit and revoke).
- **Read-only** — `SELECT`/`USAGE` only; never write/DDL privileges.
- **Least-privilege** — grant access only to the schemas/tables you want monitored.
- **Secrets via `${ENV}`** — put the password/key in an environment variable and reference it
  as `${VAR}` in `database_connection.yaml`; Comet never stores a plaintext secret.

---

## PostgreSQL
```sql
CREATE ROLE comet_readonly LOGIN PASSWORD '<strong-password>';
GRANT CONNECT ON DATABASE your_db TO comet_readonly;
GRANT USAGE ON SCHEMA public TO comet_readonly;                       -- repeat per schema
GRANT SELECT ON ALL TABLES IN SCHEMA public TO comet_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO comet_readonly;  -- future tables
```

## MySQL
```sql
CREATE USER 'comet_readonly'@'%' IDENTIFIED BY '<strong-password>';
GRANT SELECT ON your_db.* TO 'comet_readonly'@'%';
FLUSH PRIVILEGES;
```

## SQL Server (MSSQL)
```sql
CREATE LOGIN comet_readonly WITH PASSWORD = '<strong-password>';
CREATE USER comet_readonly FOR LOGIN comet_readonly;
ALTER ROLE db_datareader ADD MEMBER comet_readonly;   -- read-only across all tables
```

## Snowflake (key-pair auth recommended over a password)
```sql
USE ROLE ACCOUNTADMIN;
CREATE ROLE COMET_RO;
CREATE USER COMET_SVC RSA_PUBLIC_KEY='<your-public-key>' DEFAULT_ROLE = COMET_RO;
GRANT ROLE COMET_RO TO USER COMET_SVC;
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE COMET_RO;
GRANT USAGE ON DATABASE ANALYTICS TO ROLE COMET_RO;
GRANT USAGE ON ALL SCHEMAS IN DATABASE ANALYTICS TO ROLE COMET_RO;
GRANT SELECT ON ALL TABLES IN DATABASE ANALYTICS TO ROLE COMET_RO;
GRANT SELECT ON FUTURE TABLES IN DATABASE ANALYTICS TO ROLE COMET_RO;   -- new tables
```

---

## Then point Comet at it
In `database_connection.yaml`, reference the credential as an environment variable (never a
literal). Example (PostgreSQL):
```yaml
prod:
  type: postgresql
  host: your-db-host
  database: your_db
  username: comet_readonly
  password: ${PROD_DB_PASSWORD}      # set PROD_DB_PASSWORD in the environment
```
Run `comet push` to upload the profile. Comet validates that secrets are `${ENV}` references
and rejects literal passwords.

## Why read-only matters
Comet cannot make a database read-only — that's enforced by the grants above. Read-only is the
control that guarantees Comet (and anything that could compromise it) can never modify your
data, and least-privilege scoping bounds what it can read at all. This is especially important
for `custom_sql` checks, which run query SQL you author.
