import { Pool } from 'pg';
import { drizzle } from 'drizzle-orm/node-postgres';


// Default (main) DB
const poolMain = new Pool({
  connectionString: process.env.DATABASE_URL_TAR,
});
export const dbTAR = drizzle(poolMain);

// CVP DB
const poolCVP = new Pool({
  connectionString: process.env.DATABASE_URL_CVP,
});
export const dbCVP = drizzle(poolCVP);
