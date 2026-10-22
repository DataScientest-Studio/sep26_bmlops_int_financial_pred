-- Creates a service's own login once; its password is set on every run, so a changed
-- password in .env takes effect.
SELECT format('CREATE ROLE %I LOGIN', :'name')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'name')
\gexec

SELECT format('ALTER ROLE %I PASSWORD %L', :'name', :'password')
\gexec

-- Creates the service's database once, owned by that login.
SELECT format('CREATE DATABASE %I OWNER %I', :'name', :'name')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'name')
\gexec
