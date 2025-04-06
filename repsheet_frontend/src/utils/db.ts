import Database from "better-sqlite3";
import { resolve } from "node:path";

// TODOJS - use dirname or the equiv
const dbPath = resolve("..", "repsheet.sqlite");
const db = new Database(dbPath);
db.pragma("journal_mode = WAL");

export default db;
