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
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing } from '../theme/theme';

export default function QueueScreen({ navigation }) {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [filter, setFilter] = useState('all'); // all, queued, uploading, failed, uploaded

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
              ID: {item.id} • {item.pages?.length || 1} {t('page_count')}
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
                ? t('queue_status_uploaded')
                : isUploading
                ? t('queue_status_uploading')
                : isFailed
                ? t('queue_status_failed')
                : t('queue_status_queued')}
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
          <Text style={styles.metaText}>
            📍 {[item.village, item.tehsil, item.district].filter(Boolean).join(', ') || 'Location N/A'}
          </Text>
          <Text style={styles.metaDate}>
            {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </Text>
        </View>

        {isFailed && item.failure_reason ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorBannerText}>⚠️ {item.failure_reason}</Text>
          </View>
        ) : null}

        {/* Actions */}
        <View style={styles.actionRow}>
          {isFailed || isQueued ? (
            <Button
              title="🔄 Sync Now"
              variant="primary"
              size="sm"
              onPress={() => handleRetryItem(item.id)}
              loading={isUploading}
              style={{ flex: 1, marginRight: spacing.sm }}
            />
          ) : null}
          {isUploaded && item.server_doc_id ? (
            <Button
              title="👁️ View Details"
              variant="outline"
              size="sm"
              onPress={() => navigation.navigate('Review', { documentId: item.server_doc_id })}
              style={{ flex: 1, marginRight: spacing.sm }}
            />
          ) : null}
          <Button
            title="🗑️"
            variant="ghost"
            size="sm"
            onPress={() => handleDeleteItem(item.id)}
          />
        </View>
      </Card>
    );
  };

  return (
    <View style={styles.container}>
      {/* Header Bar */}
      <View style={styles.topBanner}>
        <View>
          <Text style={styles.bannerTitle}>{t('queue_title')}</Text>
          <Text style={styles.bannerSub}>
            {pendingCount} Pending • {uploadedCount} Synced
          </Text>
        </View>
        <Button
          title={syncing ? 'Syncing...' : '🔄 Sync All'}
          variant="saffron"
          size="sm"
          onPress={handleSyncAll}
          loading={syncing}
          disabled={pendingCount === 0 || syncing}
        />
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterRow}>
        {['all', 'queued', 'failed', 'uploaded'].map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterTab, filter === f && styles.filterTabActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
              {f.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {uploadedCount > 0 && filter === 'uploaded' ? (
        <TouchableOpacity style={styles.clearBtn} onPress={handleClearCompleted}>
          <Text style={styles.clearBtnText}>🧹 Clear Synced Cache</Text>
        </TouchableOpacity>
      ) : null}

      {loading && !syncing ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.govNavy600} />
        </View>
      ) : (
        <FlatList
          data={filteredItems}
          keyExtractor={(i) => i.id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={loadQueue}
              colors={[colors.govNavy600]}
              tintColor={colors.govNavy600}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>📦</Text>
              <Text style={styles.emptyTitle}>{t('queue_empty')}</Text>
              <Text style={styles.emptySub}>
                All captured land records are synced with the central repository.
              </Text>
              <Button
                title="📸 Scan New Record"
                variant="primary"
                style={{ marginTop: spacing.md }}
                onPress={() => navigation.navigate('Capture')}
              />
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
    backgroundColor: colors.govNavy900,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  bannerTitle: {
    fontSize: typography.sizes.lg,
    fontWeight: '700',
    color: colors.white,
  },
  bannerSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate300,
    marginTop: 2,
  },
  filterRow: {
    flexDirection: 'row',
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate200,
    paddingHorizontal: spacing.sm,
  },
  filterTab: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  filterTabActive: {
    borderBottomColor: colors.govNavy600,
  },
  filterText: {
    fontSize: typography.sizes.xs,
    fontWeight: '600',
    color: colors.slate500,
  },
  filterTextActive: {
    color: colors.govNavy600,
  },
  listContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  card: {
    marginBottom: spacing.md,
  },
  failedCard: {
    borderLeftWidth: 4,
    borderLeftColor: colors.rose600,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  cardTitle: {
    fontSize: typography.sizes.md,
    fontWeight: '700',
    color: colors.slate900,
  },
  cardSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  statusPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.full,
  },
  pillQueued: {
    backgroundColor: colors.slate100,
  },
  pillUploading: {
    backgroundColor: colors.saffron100,
  },
  pillUploaded: {
    backgroundColor: colors.emerald100,
  },
  pillFailed: {
    backgroundColor: colors.rose100,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  thumbnailRow: {
    flexDirection: 'row',
    marginTop: spacing.sm,
    gap: 6,
  },
  thumbImage: {
    width: 48,
    height: 60,
    borderRadius: radius.xs,
    backgroundColor: colors.slate200,
  },
  thumbMore: {
    width: 48,
    height: 60,
    borderRadius: radius.xs,
    backgroundColor: colors.slate800,
    justifyContent: 'center',
    alignItems: 'center',
  },
  thumbMoreText: {
    color: colors.white,
    fontSize: typography.sizes.xs,
    fontWeight: '700',
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.slate100,
  },
  metaText: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    flex: 1,
  },
  metaDate: {
    fontSize: typography.sizes.xs,
    color: colors.slate400,
    marginLeft: spacing.xs,
  },
  errorBanner: {
    marginTop: spacing.xs,
    padding: spacing.xs,
    backgroundColor: colors.rose50,
    borderRadius: radius.xs,
  },
  errorBannerText: {
    fontSize: typography.sizes.xs,
    color: colors.rose800,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  clearBtn: {
    padding: spacing.sm,
    alignItems: 'center',
    backgroundColor: colors.slate100,
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    borderRadius: radius.sm,
  },
  clearBtnText: {
    fontSize: typography.sizes.xs,
    color: colors.slate700,
    fontWeight: '600',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xxl,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: spacing.sm,
  },
  emptyTitle: {
    fontSize: typography.sizes.lg,
    fontWeight: '700',
    color: colors.slate800,
  },
  emptySub: {
    fontSize: typography.sizes.sm,
    color: colors.slate500,
    textAlign: 'center',
    marginTop: 4,
    paddingHorizontal: spacing.lg,
  },
});
