-- SETUP SCRIPT (Run as postgres/superuser)

-- 1. Create the new application database
CREATE DATABASE teia_trust_mvp;

-- 2. Create the dedicated MVP user
CREATE USER teia_trust_app WITH PASSWORD 'mvp_secure_pass_123';

-- 3. Set up permissions for the MVP database (Full Access)
\c teia_trust_mvp
GRANT ALL PRIVILEGES ON SCHEMA public TO teia_trust_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO teia_trust_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO teia_trust_app;

-- 4. Set up permissions for the Indexer database (Read-Only Access)
\c teia_ecosystem
GRANT CONNECT ON DATABASE teia_ecosystem TO teia_trust_app;
GRANT USAGE ON SCHEMA public TO teia_trust_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO teia_trust_app;
-- Ensure the user can also read the views we created
GRANT SELECT ON trust_connections TO teia_trust_app;
