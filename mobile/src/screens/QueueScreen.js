import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Image,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  getQueueItems,
  deleteQueueItem,
  clearCompletedQueueItems,
} from '../utils/queueDatabase';
import {
  syncPendingQueue,
  retrySingleItem,
  addSyncListener,
} from '../services/syncEngine';
import { useI18n } from '../i18n/i18n';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing, shadows } from '../theme/theme';

export default function QueueScreen({ navigation }) {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [filter, setFilter] = useState('all');

  const loadQueue = useCallback(async () => {
    try {
      setLoading(true);
      const rows = await getQueueItems();
      setItems(rows);
    } catch (err) {
      console.warn('Load queue error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
    const unsubscribeSync = addSyncListener((event) => {
      if (event.type === 'SYNC_START') setSyncing(true);
      if (event.type === 'SYNC_END') {
        setSyncing(false);
        loadQueue();
      }
      if (event.type === 'STATUS_CHANGE') {
        loadQueue();
      }
    });
    return unsubscribeSync;
  }, [loadQueue]);

  const handleSyncAll = async () => {
    try {
      setSyncing(true);
      await syncPendingQueue();
      await loadQueue();
    } catch (e) {
      Alert.alert('Sync Error', 'Could not sync queue items.');
    } finally {
      setSyncing(false);
    }
  };

  const handleRetryItem = async (itemId) => {
    try {
      await retrySingleItem(itemId);
      await loadQueue();
    } catch (e) {
      Alert.alert('Retry Error', 'Failed to retry upload for this record.');
    }
  };

  const handleDeleteItem = (itemId) => {
    Alert.alert(
      'Remove from Queue',
      'Are you sure you want to remove this capture from the local offline queue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            await deleteQueueItem(itemId);
            await loadQueue();
          },
        },
      ]
    );
  };

  const handleClearCompleted = async () => {
    await clearCompletedQueueItems();
    await loadQueue();
  };

  const filteredItems = items.filter((item) => {
    if (filter === 'all') return true;
    return item.status === filter;
  });

  const pendingCount = items.filter((i) => i.status === 'queued' || i.status === 'failed').length;
  const uploadedCount = items.filter((i) => i.status === 'uploaded').length;

  const renderItem = ({ item }) => {
    const isUploading = item.status === 'uploading';
    const isFailed = item.status === 'failed';
    const isQueued = item.status === 'queued';
    const isUploaded = item.status === 'uploaded';

    return (
      <Card style={[styles.card, isFailed && styles.failedCard]}>
        <View style={styles.cardHeader}>
          <View style={{ flex: 1, marginRight: spacing.xs }}>
            <Text style={styles.cardTitle} numberOfLines={1}>
              {item.title || 'Land Record Capture'}
            </Text>
            <Text style={styles.cardSub}>
              ID: #{item.id} • {item.pages?.length || 1} Page(s)
            </Text>
          </View>
          <View
            style={[
              styles.statusPill,
              isUploaded && styles.pillUploaded,
              isFailed && styles.pillFailed,
              isUploading && styles.pillUploading,
              isQueued && styles.pillQueued,
            ]}
          >
            <Text
              style={[
                styles.statusText,
                isUploaded && { color: colors.emerald800 },
                isFailed && { color: colors.rose800 },
                isUploading && { color: colors.saffron900 },
                isQueued && { color: colors.slate800 },
              ]}
            >
              {isUploaded
                ? 'SYNCED'
                : isUploading
                ? 'UPLOADING...'
                : isFailed
                ? 'FAILED'
                : 'QUEUED'}
            </Text>
          </View>
        </View>

        {/* Thumbnail Preview */}
        {item.pages && item.pages.length > 0 ? (
          <View style={styles.thumbnailRow}>
            {item.pages.slice(0, 4).map((pg, idx) => (
              <Image key={idx} source={{ uri: pg.uri }} style={styles.thumbImage} />
            ))}
            {item.pages.length > 4 ? (
              <View style={styles.thumbMore}>
                <Text style={styles.thumbMoreText}>+{item.pages.length - 4}</Text>
              </View>
            ) : null}
          </View>
        ) : null}

        {/* Location Metadata */}
        <View style={styles.metaRow}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, flex: 1 }}>
            <Ionicons name="location-outline" size={13} color={colors.slate500} />
            <Text style={styles.metaText} numberOfLines={1}>
              {[item.village, item.tehsil, item.district].filter(Boolean).join(', ') || 'Jaipur Division'}
            </Text>
          </View>
          <Text style={styles.metaDate}>
            {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </Text>
        </View>

        {isFailed && item.failure_reason ? (
          <View style={styles.errorBanner}>
            <Ionicons name="alert-circle-outline" size={14} color={colors.rose600} />
            <Text style={styles.errorBannerText}>{item.failure_reason}</Text>
          </View>
        ) : null}

        {/* Actions */}
        <View style={styles.actionRow}>
          {isFailed || isQueued ? (
            <TouchableOpacity
              style={styles.syncItemBtn}
              onPress={() => handleRetryItem(item.id)}
            >
              <Ionicons name="sync-outline" size={14} color={colors.white} />
              <Text style={styles.syncItemBtnText}>Sync Now</Text>
            </TouchableOpacity>
          ) : null}

          {isUploaded && item.server_doc_id ? (
            <TouchableOpacity
              style={styles.viewDeedBtn}
              onPress={() => navigation.navigate('Review', { documentId: item.server_doc_id })}
            >
              <Ionicons name="eye-outline" size={14} color={colors.govNavy700} />
              <Text style={styles.viewDeedBtnText}>Inspect Ingested Deed</Text>
            </TouchableOpacity>
          ) : null}

          <TouchableOpacity
            style={styles.deleteIconBtn}
            onPress={() => handleDeleteItem(item.id)}
          >
            <Ionicons name="trash-outline" size={16} color={colors.rose600} />
          </TouchableOpacity>
        </View>
      </Card>
    );
  };

  return (
    <View style={styles.container}>
      {/* Top Sovereign Summary */}
      <View style={styles.topBanner}>
        <View>
          <Text style={styles.bannerTitle}>Offline Sync Engine</Text>
          <Text style={styles.bannerSub}>
            {pendingCount} Pending Upload • {uploadedCount} Synced
          </Text>
        </View>
        <TouchableOpacity
          style={[styles.syncAllBtn, (pendingCount === 0 || syncing) && styles.syncAllBtnDisabled]}
          onPress={handleSyncAll}
          disabled={pendingCount === 0 || syncing}
        >
          {syncing ? (
            <ActivityIndicator size="small" color={colors.govNavy950} />
          ) : (
            <>
              <Ionicons name="cloud-upload" size={16} color={colors.govNavy950} />
              <Text style={styles.syncAllText}>Sync All</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterRow}>
        {[
          { id: 'all', label: 'All' },
          { id: 'queued', label: 'Queued' },
          { id: 'failed', label: 'Failed' },
          { id: 'uploaded', label: 'Synced' },
        ].map((f) => (
          <TouchableOpacity
            key={f.id}
            style={[styles.filterTab, filter === f.id && styles.filterTabActive]}
            onPress={() => setFilter(f.id)}
          >
            <Text style={[styles.filterText, filter === f.id && styles.filterTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.saffron500} />
        </View>
      ) : (
        <FlatList
          data={filteredItems}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={loadQueue}
              colors={[colors.saffron500]}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyBox}>
              <Ionicons name="file-tray-outline" size={44} color={colors.slate300} />
              <Text style={styles.emptyTitle}>Offline Queue is Empty</Text>
              <Text style={styles.emptySub}>Captures taken in the field without network will appear here</Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPage,
  },
  topBanner: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.white,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderCard,
  },
  bannerTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  bannerSub: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 2,
  },
  syncAllBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.saffron500,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.full,
  },
  syncAllBtnDisabled: {
    opacity: 0.5,
  },
  syncAllText: {
    fontSize: 12,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: 8,
  },
  filterTab: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.full,
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.borderCard,
  },
  filterTabActive: {
    backgroundColor: colors.govNavy900,
    borderColor: colors.govNavy900,
  },
  filterText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.slate600,
  },
  filterTextActive: {
    color: colors.white,
    fontWeight: '700',
  },
  listContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    ...shadows.sm,
  },
  failedCard: {
    borderColor: colors.rose300,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  cardSub: {
    fontSize: 10.5,
    color: colors.slate500,
    marginTop: 1,
  },
  statusPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
  },
  pillUploaded: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
  },
  pillUploading: {
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
  },
  pillFailed: {
    backgroundColor: 'rgba(220, 38, 38, 0.15)',
  },
  pillQueued: {
    backgroundColor: colors.slate100,
  },
  statusText: {
    fontSize: 9.5,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  thumbnailRow: {
    flexDirection: 'row',
    gap: 6,
    marginVertical: 8,
  },
  thumbImage: {
    width: 48,
    height: 64,
    borderRadius: radius.xs,
    backgroundColor: colors.slate100,
  },
  thumbMore: {
    width: 48,
    height: 64,
    borderRadius: radius.xs,
    backgroundColor: colors.govNavy800,
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbMoreText: {
    color: colors.white,
    fontSize: 12,
    fontWeight: '800',
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: colors.slate100,
  },
  metaText: {
    fontSize: 11,
    color: colors.slate600,
    fontWeight: '500',
  },
  metaDate: {
    fontSize: 10,
    color: colors.slate400,
  },
  errorBanner: {
    backgroundColor: colors.rose50,
    borderRadius: radius.xs,
    padding: 6,
    marginTop: 8,
  },
  errorBannerText: {
    color: colors.rose700,
    fontSize: 11,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: spacing.md,
  },
  syncItemBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: colors.govNavy900,
    paddingVertical: 8,
    borderRadius: radius.sm,
  },
  syncItemBtnText: {
    color: colors.white,
    fontSize: 11.5,
    fontWeight: '700',
  },
  viewDeedBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: colors.govNavy50,
    borderColor: colors.govNavy100,
    borderWidth: 1,
    paddingVertical: 8,
    borderRadius: radius.sm,
  },
  viewDeedBtnText: {
    color: colors.govNavy700,
    fontSize: 11.5,
    fontWeight: '700',
  },
  deleteIconBtn: {
    width: 34,
    height: 34,
    borderRadius: radius.sm,
    backgroundColor: colors.rose50,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.rose100,
  },
  centerContainer: {
    paddingVertical: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyBox: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.slate600,
    marginTop: 10,
  },
  emptySub: {
    fontSize: 11,
    color: colors.slate400,
    marginTop: 2,
    textAlign: 'center',
  },
});
