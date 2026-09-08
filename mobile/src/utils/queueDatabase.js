import * as SQLite from 'expo-sqlite';
import * as FileSystem from 'expo-file-system';

let dbInstance = null;

export async function getDatabase() {
  if (!dbInstance) {
    dbInstance = await SQLite.openDatabaseAsync('bhoomi_queue.db');
    await dbInstance.execAsync(`
      PRAGMA journal_mode = WAL;
      CREATE TABLE IF NOT EXISTS capture_queue (
        id TEXT PRIMARY KEY,
        title TEXT,
        district TEXT,
        tehsil TEXT,
        village TEXT,
        pages_json TEXT,
        status TEXT,
        failure_reason TEXT,
        retry_count INTEGER DEFAULT 0,
        server_doc_id INTEGER,
        created_at TEXT,
        updated_at TEXT
      );
    `);
  }
  return dbInstance;
}

export async function copyImageToLocalStorage(sourceUri, localId, pageIndex) {
  try {
    const dir = `${FileSystem.documentDirectory}captured_queue/${localId}/`;
    await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
    const ext = sourceUri.split('.').pop() || 'jpg';
    const destination = `${dir}page_${pageIndex}.${ext}`;
    await FileSystem.copyAsync({ from: sourceUri, to: destination });
    return destination;
  } catch (err) {
    console.warn('Failed to copy image to local storage:', err);
    return sourceUri;
  }
}

export async function addToQueue(queueData) {
  const db = await getDatabase();
  const id = `local_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
  const now = new Date().toISOString();

  // Save image files locally
  const savedPages = [];
  if (Array.isArray(queueData.pages)) {
    for (let i = 0; i < queueData.pages.length; i++) {
      const page = queueData.pages[i];
      const localUri = await copyImageToLocalStorage(page.uri, id, i);
      savedPages.push({ ...page, uri: localUri });
    }
  }

  const pagesJson = JSON.stringify(savedPages);

  await db.runAsync(
    `INSERT INTO capture_queue 
    (id, title, district, tehsil, village, pages_json, status, failure_reason, retry_count, server_doc_id, created_at, updated_at) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      id,
      queueData.title || 'Land Record Capture',
      queueData.district || 'Patna',
      queueData.tehsil || '',
      queueData.village || '',
      pagesJson,
      'queued',
      null,
      0,
      null,
      now,
      now,
    ]
  );

  return { id, ...queueData, pages: savedPages, status: 'queued', created_at: now };
}

export async function getQueueItems() {
  const db = await getDatabase();
  const rows = await db.getAllAsync('SELECT * FROM capture_queue ORDER BY created_at DESC');
  return rows.map((r) => ({
    ...r,
    pages: r.pages_json ? JSON.parse(r.pages_json) : [],
  }));
}

export async function updateQueueStatus(id, status, failureReason = null, serverDocId = null) {
  const db = await getDatabase();
  const now = new Date().toISOString();
  await db.runAsync(
    `UPDATE capture_queue 
     SET status = ?, failure_reason = ?, server_doc_id = COALESCE(?, server_doc_id), updated_at = ? 
     WHERE id = ?`,
    [status, failureReason, serverDocId, now, id]
  );
}

export async function deleteQueueItem(id) {
  const db = await getDatabase();
  const itemDir = `${FileSystem.documentDirectory}captured_queue/${id}/`;
  await FileSystem.deleteAsync(itemDir, { idempotent: true }).catch(() => {});
  await db.runAsync('DELETE FROM capture_queue WHERE id = ?', [id]);
}

export async function getQueuedCount() {
  try {
    const db = await getDatabase();
    const result = await db.getFirstAsync(
      "SELECT COUNT(*) as count FROM capture_queue WHERE status = 'queued'"
    );
    return result?.count ?? 0;
  } catch {
    return 0;
  }
}

