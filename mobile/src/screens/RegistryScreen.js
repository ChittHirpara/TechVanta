import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Animated,
} from 'react-native';
import { documentsApi, notificationsApi } from '../api/client';
import { getQueuedCount } from '../utils/queueDatabase';
import { useI18n } from '../i18n/i18n';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Input from '../components/common/Input';
import { colors, radius, typography, spacing } from '../theme/theme';

const STATUS_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'needs_review', label: 'Needs Review' },
  { id: 'verified', label: 'Verified' },
  { id: 'processing', label: 'Processing' },
  { id: 'flagged', label: 'Flagged' },
];

// Pan-India dynamic district filters extracted from loaded records

export default function RegistryScreen({ navigation }) {
  const { t } = useI18n();
  const [documents, setDocuments] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [queuedCount, setQueuedCount] = useState(0);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [districtFilter, setDistrictFilter] = useState('All Districts');

  // FAB pulse animation
  const fabScale = React.useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(fabScale, { toValue: 1.08, duration: 900, useNativeDriver: true }),
        Animated.timing(fabScale, { toValue: 1, duration: 900, useNativeDriver: true }),
      ])
    );
    pulse.start();
    return () => pulse.stop();
  }, [fabScale]);

  const fetchDocuments = useCallback(async () => {
    try {
      setError(null);
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (districtFilter !== 'All Districts') params.district = districtFilter;
      if (search.trim()) params.search = search.trim();

      const res = await documentsApi.list(params);
      setDocuments(res.items || res || []);

      // Fetch status notifications
      try {
        const notifs = await notificationsApi.getNotifications(5);
        setNotifications(notifs || []);
      } catch (e) {}
    } catch (err) {
      setError(err.message || 'Failed to fetch land records registry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter, districtFilter, search]);

  const loadQueueCount = useCallback(async () => {
    try {
      const count = await getQueuedCount();
      setQueuedCount(count);
    } catch {
      // silently ignore — DB may not be ready
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
    loadQueueCount();
  }, [fetchDocuments, loadQueueCount]);

  // Refresh queue count whenever the screen is focused
  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => {
      loadQueueCount();
      fetchDocuments();
    });
    return unsubscribe;
  }, [navigation, loadQueueCount, fetchDocuments]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchDocuments();
    loadQueueCount();
  };

  const renderItem = ({ item }) => (
    <Card style={styles.recordCard}>
      <View style={styles.cardHeader}>
        <View style={{ flex: 1, marginRight: spacing.xs }}>
          <Text style={styles.docTitle} numberOfLines={1}>
            {item.title || `Land Record #${item.id}`}
          </Text>
          <Text style={styles.docSub}>
            #{item.id} · {item.district || 'N/A'}
          </Text>
        </View>
        <Badge status={item.status} />
      </View>

      <View style={styles.metaRow}>
        <Text style={styles.metaText}>
          📅 {item.created_at ? new Date(item.created_at).toLocaleDateString('en-IN') : 'Recent'}
        </Text>
        <Text style={styles.metaText}>
          👤 {item.uploaded_by_user?.username || 'Field Officer'}
        </Text>
      </View>

      <View style={styles.cardActions}>
        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnOutline]}
          onPress={() => navigation.navigate('Audit', { documentId: item.id })}
          activeOpacity={0.75}
        >
          <Text style={styles.actionBtnOutlineText}>Audit Trail</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnPrimary]}
          onPress={() => navigation.navigate('Review', { documentId: item.id })}
          activeOpacity={0.75}
        >
          <Text style={styles.actionBtnPrimaryText}>View Details</Text>
        </TouchableOpacity>
      </View>
    </Card>
  );

  const ListHeader = () => (
    <View style={styles.filterSection}>
      <View style={styles.titleRow}>
        <View>
          <Text style={styles.screenTitle}>{t('app_title')} - {t('nav_registry')}</Text>
          <Text style={styles.screenSub}>{t('app_subtitle')}</Text>
        </View>
        {queuedCount > 0 && (
          <TouchableOpacity
            style={styles.queueBadge}
            onPress={() => navigation.navigate('Queue')}
            activeOpacity={0.8}
          >
            <Text style={styles.queueBadgeText}>📦 {queuedCount} queued</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Notifications Alert Banner if present */}
      {notifications.length > 0 && (
        <View style={styles.notifBanner}>
          <Text style={styles.notifTitle}>🔔 Latest Status Alert:</Text>
          <Text style={styles.notifMessage}>{notifications[0].message}</Text>
        </View>
      )}

      <Input
        value={search}
        onChangeText={setSearch}
        placeholder="🔍 Search owner, Khasra no., title..."
        style={{ marginBottom: spacing.xs, marginTop: spacing.xs }}
      />

      {/* Status Filter Chips */}
      <FlatList
        horizontal
        data={STATUS_FILTERS}
        keyExtractor={(item) => item.id}
        showsHorizontalScrollIndicator={false}
        style={styles.chipScroll}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.chip, statusFilter === item.id && styles.chipActiveSaffron]}
            onPress={() => setStatusFilter(item.id)}
          >
            <Text style={[styles.chipText, statusFilter === item.id && styles.chipTextActive]}>
              {item.label}
            </Text>
          </TouchableOpacity>
        )}
      />

      {/* District Filter Chips */}
      {/* Dynamic District Filters across all records in India */}
      {(() => {
        const uniqueDistricts = Array.from(new Set(documents.map((d) => d.district).filter(Boolean)));
        if (uniqueDistricts.length <= 1) return null;
        const allFilters = ['All Districts', ...uniqueDistricts];
        return (
          <FlatList
            horizontal
            data={allFilters}
            keyExtractor={(item) => item}
            showsHorizontalScrollIndicator={false}
            style={styles.chipScroll}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={[styles.chip, districtFilter === item && styles.chipActiveNavy]}
                onPress={() => setDistrictFilter(item)}
              >
                <Text style={[styles.chipText, districtFilter === item && styles.chipTextActive]}>
                  {item}
                </Text>
              </TouchableOpacity>
            )}
          />
        );
      })()}
    </View>
  );

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
          <TouchableOpacity onPress={fetchDocuments}>
            <Text style={styles.errorRetry}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {loading && !refreshing ? (
        <>
          <ListHeader />
          <View style={styles.centerContainer}>
            <ActivityIndicator size="large" color={colors.govNavy600} />
            <Text style={styles.loadingText}>Fetching registry records…</Text>
          </View>
        </>
      ) : (
        <FlatList
          data={documents}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          ListHeaderComponent={<ListHeader />}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={[colors.govNavy600]}
              tintColor={colors.govNavy600}
            />
          }
          ListEmptyComponent={
            <Card style={styles.emptyCard}>
              <Text style={styles.emptyIcon}>📋</Text>
              <Text style={styles.emptyTitle}>No records found</Text>
              <Text style={styles.emptySub}>
                Adjust your filters or pull down to refresh.{'\n'}
                Tap the{' '}
                <Text style={{ color: colors.govNavy700, fontWeight: '700' }}>📷 Capture</Text>
                {' '}button to submit a new document.
              </Text>
            </Card>
          }
        />
      )}

      {/* Floating Action Button — Capture new document */}
      <Animated.View style={[styles.fabWrap, { transform: [{ scale: fabScale }] }]}>
        <TouchableOpacity
          style={styles.fab}
          onPress={() => navigation.navigate('Capture')}
          activeOpacity={0.85}
        >
          <Text style={styles.fabIcon}>📷</Text>
          <Text style={styles.fabLabel}>Capture</Text>
        </TouchableOpacity>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPage,
  },

  /* ── Filter header ── */
  filterSection: {
    backgroundColor: colors.white,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderCard,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  screenTitle: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  screenSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
  },
  queueBadge: {
    backgroundColor: colors.saffron600,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.full,
    marginTop: 2,
  },
  queueBadgeText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: typography.weights.bold,
  },
  chipScroll: { marginTop: 4, marginBottom: 2 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: radius.full,
    backgroundColor: colors.slate100,
    borderColor: colors.slate300,
    borderWidth: 1,
    marginRight: 6,
  },
  chipActiveSaffron: { backgroundColor: colors.saffron600, borderColor: colors.saffron600 },
  chipActiveNavy: { backgroundColor: colors.govNavy900, borderColor: colors.govNavy900 },
  chipText: { fontSize: 12, color: colors.slate700, fontWeight: typography.weights.medium },
  chipTextActive: { color: colors.white, fontWeight: typography.weights.bold },

  /* ── List ── */
  listContent: { padding: spacing.md, paddingBottom: 100 },

  /* ── States ── */
  centerContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: spacing.xl },
  loadingText: { marginTop: spacing.md, color: colors.slate600, fontSize: typography.sizes.sm },
  errorBanner: {
    backgroundColor: colors.rose50,
    borderBottomWidth: 1,
    borderColor: colors.rose300,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  errorText: { color: colors.rose800, fontSize: typography.sizes.xs, flex: 1 },
  errorRetry: {
    color: colors.govNavy600,
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.bold,
    marginLeft: spacing.sm,
  },

  /* ── Cards ── */
  recordCard: { marginBottom: spacing.sm, padding: spacing.md },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.xs,
  },
  docTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  docSub: { fontSize: typography.sizes.xs, color: colors.slate500, marginTop: 2 },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.slate100,
    marginVertical: spacing.xs,
  },
  metaText: { fontSize: typography.sizes.xs, color: colors.slate600 },
  cardActions: { flexDirection: 'row', gap: spacing.xs, marginTop: spacing.xs },
  actionBtn: {
    flex: 1,
    paddingVertical: 9,
    borderRadius: radius.md,
    alignItems: 'center',
  },
  actionBtnOutline: { borderWidth: 1, borderColor: colors.govNavy300 },
  actionBtnOutlineText: {
    fontSize: 12,
    color: colors.govNavy700,
    fontWeight: typography.weights.semibold,
  },
  actionBtnPrimary: { backgroundColor: colors.govNavy900 },
  actionBtnPrimaryText: { fontSize: 12, color: colors.white, fontWeight: typography.weights.bold },

  /* ── Empty ── */
  emptyCard: { alignItems: 'center', padding: spacing.xl, marginTop: spacing.lg },
  emptyIcon: { fontSize: 36, marginBottom: spacing.sm },
  emptyTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  emptySub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    textAlign: 'center',
    marginTop: 4,
    lineHeight: 18,
  },

  /* ── FAB ── */
  fabWrap: {
    position: 'absolute',
    bottom: 28,
    right: 22,
    shadowColor: colors.govNavy900,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 10,
  },
  fab: {
    backgroundColor: colors.govNavy900,
    borderRadius: 32,
    paddingHorizontal: 22,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 2,
    borderColor: colors.saffron500,
  },
  fabIcon: { fontSize: 20 },
  fabLabel: {
    color: colors.white,
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    letterSpacing: 0.5,
  },
  notifBanner: {
    backgroundColor: colors.emerald50,
    borderColor: colors.emerald500,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.sm,
    marginTop: spacing.xs,
    marginBottom: spacing.xs,
  },
  notifTitle: {
    fontSize: typography.sizes.xs,
    fontWeight: '700',
    color: colors.emerald800,
  },
  notifMessage: {
    fontSize: typography.sizes.xs,
    color: colors.emerald700,
    marginTop: 2,
  },
});

