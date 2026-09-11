import NetInfo from '@react-native-community/netinfo';
import { getQueueItems, updateQueueStatus } from '../utils/queueDatabase';
import { uploadWithProgress } from '../api/client';

let isSyncing = false;
let syncListeners = new Set();

export function addSyncListener(listener) {
  syncListeners.add(listener);
  return () => syncListeners.delete(listener);
}

function notifySyncListeners(event) {
  syncListeners.forEach((fn) => {
    try {
      fn(event);
    } catch (e) {
      console.warn('Sync listener error:', e);
    }
  });
}

export async function processQueueItem(item, onProgressCallback) {
  try {
    await updateQueueStatus(item.id, 'uploading');
    notifySyncListeners({ type: 'STATUS_CHANGE', id: item.id, status: 'uploading' });

    const pages = item.pages || [];
    const mainPage = pages[0] || {};
    const uri = mainPage.uri;

    if (!uri) {
      throw new Error('No valid image file found for document.');
    }

    const formData = new FormData();
    const filename = uri.split('/').pop() || 'record.jpg';
    const match = /\.(\w+)$/.exec(filename);
    const type = match ? `image/${match[1]}` : 'image/jpeg';

    formData.append('file', {
      uri,
      name: filename,
      type,
    });

    let displayTitle = item.title || 'Land Record';
    if (item.village || item.tehsil) {
      const locDetails = [item.village, item.tehsil].filter(Boolean).join(', ');
      displayTitle += ` (${locDetails})`;
    }
    if (pages.length > 1) {
      displayTitle += ` - ${pages.length} Pages`;
    }

    formData.append('title', displayTitle);
    if (item.district) {
      formData.append('district', item.district);
    }
    if (item.tehsil) {
      formData.append('tehsil', item.tehsil);
    }
    if (item.village) {
      formData.append('village', item.village);
    }
    // Pass client_capture_id to guarantee idempotency on retries
    formData.append('client_capture_id', item.id);

    const res = await uploadWithProgress(formData, (percent) => {
      if (onProgressCallback) onProgressCallback(percent);
      notifySyncListeners({ type: 'PROGRESS', id: item.id, progress: percent });
    });

    const serverDocId = res?.id;
    if (!serverDocId) {
      throw new Error('Server returned invalid document response.');
    }

    await updateQueueStatus(item.id, 'uploaded', null, serverDocId);
    notifySyncListeners({ type: 'STATUS_CHANGE', id: item.id, status: 'uploaded', serverDocId });
    return { success: true, serverDocId };
  } catch (err) {
    const errorMsg = err.message || 'Upload failed due to network or server error.';
    await updateQueueStatus(item.id, 'failed', errorMsg);
    notifySyncListeners({ type: 'STATUS_CHANGE', id: item.id, status: 'failed', error: errorMsg });
    return { success: false, error: errorMsg };
  }
}

export async function syncPendingQueue() {
  if (isSyncing) return;

  const netState = await NetInfo.fetch();
  if (!netState.isConnected) return;

  try {
    isSyncing = true;
    notifySyncListeners({ type: 'SYNC_START' });

    const allItems = await getQueueItems();
    const pendingItems = allItems.filter((i) => i.status === 'queued' || i.status === 'failed');

    for (let index = 0; index < pendingItems.length; index++) {
      const item = pendingItems[index];
      // Exponential backoff with random jitter between queue batch uploads to protect network
      if (index > 0) {
        const jitter = Math.floor(Math.random() * 500) + 200;
        await new Promise((resolve) => setTimeout(resolve, jitter));
      }
      await processQueueItem(item);
    }
  } catch (err) {
    console.warn('Sync pending queue error:', err);
  } finally {
    isSyncing = false;
    notifySyncListeners({ type: 'SYNC_END' });
  }
}

export async function retrySingleItem(itemId) {
  const allItems = await getQueueItems();
  const item = allItems.find((i) => i.id === itemId);
  if (!item) return;
  return await processQueueItem(item);
}

export function initAutoSyncEngine() {
  const unsubscribe = NetInfo.addEventListener((state) => {
    if (state.isConnected) {
      syncPendingQueue();
    }
  });
  return unsubscribe;
}
