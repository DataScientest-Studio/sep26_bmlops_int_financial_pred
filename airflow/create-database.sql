-- Creates Airflow's own login once; its password is set on every run, so a changed
-- AIRFLOW_DB_PASSWORD takes effect.
SELECT 'CREATE ROLE airflow LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow')
\gexec

ALTER ROLE airflow PASSWORD :'password';

-- Creates Airflow's database once, owned by that login.
SELECT 'CREATE DATABASE airflow OWNER airflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')
\gexec
