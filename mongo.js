import pkg from 'pg';
import dotenv from 'dotenv';

dotenv.config();

process.env.NODE_TLS_REJECT_UNAUTHORIZED = process.env.NODE_TLS_REJECT_UNAUTHORIZED || '0';

const { Pool } = pkg;

const connectionString = process.env.DATABASE_URL || process.env.PG_CONNECTION_STRING;

const poolConfig = {};

if (connectionString) {
  poolConfig.connectionString = connectionString;
} else {
  poolConfig.user = process.env.DATABASE_USER || process.env.PG_USER;
  poolConfig.host = process.env.DATABASE_HOST || process.env.PG_HOST;
  poolConfig.database = process.env.DATABASE_NAME || process.env.PG_DATABASE;
  poolConfig.password = process.env.DATABASE_PASSWORD || process.env.PG_PASSWORD;
  if (process.env.DATABASE_PORT || process.env.PG_PORT) {
    poolConfig.port = Number(process.env.DATABASE_PORT || process.env.PG_PORT);
  }
}

const sslEnv = process.env.DATABASE_SSL || process.env.PG_SSL;
if (sslEnv === 'false') {
  poolConfig.ssl = false;
} else {
  poolConfig.ssl = { rejectUnauthorized: false };
}

const redactedConfig = {
  ...poolConfig,
  connectionString: poolConfig.connectionString ? '[REDACTED]' : undefined,
};
console.log('[PostgreSQL] Pool configuration:', redactedConfig);

const pool = new Pool(poolConfig);

export default pool;
