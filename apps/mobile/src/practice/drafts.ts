import * as SQLite from "expo-sqlite";

export interface LocalPracticeDraft {
  sessionId: string;
  questionSlug: string;
  sourceCode: string;
  elapsedSeconds: number;
  localUpdatedAt: number;
  serverUpdatedAt?: string;
}

let databasePromise: Promise<SQLite.SQLiteDatabase> | null = null;

async function database() {
  if (!databasePromise) {
    databasePromise = SQLite.openDatabaseAsync("rigor-local.db").then(async (db) => {
      await db.execAsync(`
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS practice_drafts (
          session_id TEXT PRIMARY KEY NOT NULL,
          question_slug TEXT NOT NULL,
          source_code TEXT NOT NULL,
          elapsed_seconds INTEGER NOT NULL DEFAULT 0,
          local_updated_at INTEGER NOT NULL,
          server_updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS practice_drafts_question_slug_idx
          ON practice_drafts(question_slug);
      `);
      return db;
    });
  }
  return databasePromise;
}

interface DraftRow {
  session_id: string;
  question_slug: string;
  source_code: string;
  elapsed_seconds: number;
  local_updated_at: number;
  server_updated_at: string | null;
}

function toDraft(row: DraftRow): LocalPracticeDraft {
  return {
    sessionId: row.session_id,
    questionSlug: row.question_slug,
    sourceCode: row.source_code,
    elapsedSeconds: row.elapsed_seconds,
    localUpdatedAt: row.local_updated_at,
    ...(row.server_updated_at ? { serverUpdatedAt: row.server_updated_at } : {}),
  };
}

export async function readLocalDraft(sessionId: string) {
  const db = await database();
  const row = await db.getFirstAsync<DraftRow>(
    `SELECT session_id, question_slug, source_code, elapsed_seconds,
            local_updated_at, server_updated_at
       FROM practice_drafts
      WHERE session_id = ?`,
    sessionId,
  );
  return row ? toDraft(row) : null;
}

export async function saveLocalDraft(draft: LocalPracticeDraft) {
  const db = await database();
  await db.runAsync(
    `INSERT INTO practice_drafts (
       session_id, question_slug, source_code, elapsed_seconds,
       local_updated_at, server_updated_at
     ) VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(session_id) DO UPDATE SET
       question_slug = excluded.question_slug,
       source_code = excluded.source_code,
       elapsed_seconds = excluded.elapsed_seconds,
       local_updated_at = excluded.local_updated_at,
       server_updated_at = excluded.server_updated_at`,
    draft.sessionId,
    draft.questionSlug,
    draft.sourceCode,
    draft.elapsedSeconds,
    draft.localUpdatedAt,
    draft.serverUpdatedAt ?? null,
  );
}

export async function removeLocalDraft(sessionId: string) {
  const db = await database();
  await db.runAsync("DELETE FROM practice_drafts WHERE session_id = ?", sessionId);
}

export function shouldRestoreLocalDraft(
  local: LocalPracticeDraft,
  serverUpdatedAt: string,
): boolean {
  const serverTime = Date.parse(serverUpdatedAt);
  if (!Number.isFinite(serverTime)) return true;
  return local.localUpdatedAt > serverTime;
}
