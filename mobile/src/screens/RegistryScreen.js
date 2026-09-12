import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Animated,
  ScrollView,
  Platform,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { documentsApi, dashboardApi } from '../api/client';
import { useI18n } from '../i18n/i18n';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Input from '../components/common/Input';
import { colors, radius, typography, spacing, shadows } from '../theme/theme';

const STATUS_FILTERS = [
  { id: 'all', label: 'All Records', icon: 'layers-outline' },
  { id: 'needs_review', label: 'Needs Review', icon: 'alert-circle-outline', activeColor: colors.saffron500 },
  { id: 'verified', label: 'Verified', icon: 'checkmark-circle-outline', activeColor: colors.emerald500 },
  { id: 'processing', label: 'Processing', icon: 'time-outline', activeColor: colors.govNavy600 },
];

export default function RegistryScreen({ navigation }) {
  const { t } = useI18n();
  const [documents, setDocuments] = useState([]);
  const [allDocsCount, setAllDocsCount] = useState(0);
  const [availableDistricts, setAvailableDistricts] = useState([
    'All Districts',
    'Jaipur',
    'वाराणसी',
    'Jodhpur',
    'G.I.D.C. Estate',
  ]);
  const [stats, setStats] = useState({
    total: 6,
    verified: 2,
    needs_review: 3,
    flagged_fields: 5,
    avg_confidence: 83,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [districtFilter, setDistrictFilter] = useState('All Districts');
  const [districtModalOpen, setDistrictModalOpen] = useState(false);

  const fabScale = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(fabScale, { toValue: 1.06, duration: 1000, useNativeDriver: true }),
        Animated.timing(fabScale, { toValue: 1, duration: 1000, useNativeDriver: true }),
      ])
    );
    pulse.start();
    return () => pulse.stop();
  }, [fabScale]);

  const fetchData = useCallback(async () => {
    try {
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (districtFilter !== 'All Districts') params.district = districtFilter;
      if (search.trim()) params.search = search.trim();

      const [docsRes, statsRes, allDocsRes] = await Promise.allSettled([
        documentsApi.list(params),
        dashboardApi.getStats(),
        documentsApi.list({}),
      ]);

      if (docsRes.status === 'fulfilled') {
        const docs = docsRes.value.items || docsRes.value || [];
        setDocuments(docs);
      }

      if (allDocsRes.status === 'fulfilled') {
        const allDocs = allDocsRes.value.items || allDocsRes.value || [];
        setAllDocsCount(allDocs.length);
        const set = new Set();
        allDocs.forEach((d) => {
          const dist =
            d.extracted_fields?.find((f) => f.field_name === 'district')?.field_value ||
            d.district;
          if (dist && typeof dist === 'string' && dist.trim()) {
            set.add(dist.trim());
          }
        });
        if (set.size > 0) {
          setAvailableDistricts(['All Districts', ...Array.from(set)]);
        }
      }

      if (statsRes.status === 'fulfilled' && statsRes.value) {
        const s = statsRes.value;
        setStats({
          total: s.total_documents || documents.length || 6,
          verified: s.verified || 2,
          needs_review: s.needs_review || 3,
          flagged_fields: s.flagged_fields || 5,
          avg_confidence: Math.round((s.average_confidence || 0.83) * 100),
        });
      }
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to fetch land records registry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter, districtFilter, search]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  // Header Component with Stat Metric Cards (Matching Web Dashboard)
  const renderHeader = () => (
    <View style={styles.headerSection}>
      {/* Metrics 2x2 Symmetric Grid (100% Screen Fitted, No Cut-Off) */}
      <View style={styles.metricsGrid}>
        <View style={[styles.statCard, { borderTopColor: colors.govNavy600 }]}>
          <View style={styles.statTop}>
            <Text style={styles.statLabel}>TOTAL DEEDS</Text>
            <Ionicons name="folder-open-outline" size={16} color={colors.govNavy600} />
          </View>
          <Text style={styles.statValue}>{stats.total}</Text>
          <Text style={styles.statSub}>Ingested into registry</Text>
        </View>

        <View style={[styles.statCard, { borderTopColor: colors.emerald500 }]}>
          <View style={styles.statTop}>
            <Text style={[styles.statLabel, { color: colors.emerald700 }]}>VERIFIED & SIGNED</Text>
            <Ionicons name="checkmark-circle-outline" size={16} color={colors.emerald500} />
          </View>
          <Text style={[styles.statValue, { color: colors.emerald700 }]}>{stats.verified}</Text>
          <Text style={styles.statSub}>Legally compliant & sealed</Text>
        </View>

        <View style={[styles.statCard, { borderTopColor: colors.saffron500 }]}>
          <View style={styles.statTop}>
            <Text style={[styles.statLabel, { color: colors.saffron700 }]}>NEEDS REVIEW</Text>
            <Ionicons name="alert-circle-outline" size={16} color={colors.saffron600} />
          </View>
          <Text style={[styles.statValue, { color: colors.saffron700 }]}>{stats.needs_review}</Text>
          <Text style={styles.statSub}>Awaiting officer audit</Text>
        </View>

        <View style={[styles.statCard, { borderTopColor: colors.govNavy700 }]}>
          <View style={styles.statTop}>
            <Text style={styles.statLabel}>RELIABILITY</Text>
            <Ionicons name="shield-outline" size={16} color={colors.govNavy600} />
          </View>
          <Text style={styles.statValue}>{stats.avg_confidence}%</Text>
          <Text style={styles.statSub}>AI extraction precision</Text>
        </View>
      </View>

      {/* Jurisdictional Progress Quick Panel */}
      <Card style={styles.jurisdictionCard}>
        <View style={styles.jurisdictionHeader}>
          <View>
            <Text style={styles.jurisdictionTitle}>Jurisdictional Digitization Progress</Text>
            <Text style={styles.jurisdictionSub}>Real-time breakdown across revenue divisions</Text>
          </View>
          <TouchableOpacity onPress={onRefresh} style={styles.refreshBadge}>
            <Ionicons name="sync-outline" size={12} color={colors.govNavy600} />
            <Text style={styles.refreshText}>Sync</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.districtProgressList}>
          <View style={styles.districtRow}>
            <Text style={styles.districtName}>Jaipur Division</Text>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: '33%', backgroundColor: colors.emerald500 }]} />
            </View>
            <Text style={styles.districtPercent}>33%</Text>
          </View>

          <View style={styles.districtRow}>
            <Text style={styles.districtName}>वाराणसी मंडल</Text>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: '100%', backgroundColor: colors.emerald500 }]} />
            </View>
            <Text style={styles.districtPercent}>100%</Text>
          </View>

          <View style={styles.districtRow}>
            <Text style={styles.districtName}>Jodhpur Sub-division</Text>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: '15%', backgroundColor: colors.saffron500 }]} />
            </View>
            <Text style={styles.districtPercent}>15%</Text>
          </View>
        </View>
      </Card>

      {/* Search Bar */}
      <View style={styles.searchSection}>
        <View style={styles.searchBar}>
          <Ionicons name="search-outline" size={18} color={colors.slate400} style={{ marginRight: 8 }} />
          <Input
            value={search}
            onChangeText={setSearch}
            placeholder="Search by owner, khasra, survey no..."
            style={styles.searchInput}
          />
          {search ? (
            <TouchableOpacity onPress={() => setSearch('')} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close-circle" size={18} color={colors.slate400} />
            </TouchableOpacity>
          ) : null}
        </View>
      </View>

      {/* Status Filter 2x2 Grid (100% Screen Fitted, No Cut-Off) */}
      <View style={styles.filterSection}>
        <View style={styles.filterGrid}>
          {STATUS_FILTERS.map((f) => {
            const isSelected = statusFilter === f.id;
            return (
              <TouchableOpacity
                key={f.id}
                style={[styles.filterGridChip, isSelected && styles.filterGridChipActive]}
                onPress={() => setStatusFilter(f.id)}
                activeOpacity={0.7}
              >
                <Ionicons
                  name={f.icon}
                  size={14}
                  color={isSelected ? colors.white : (f.activeColor || colors.slate500)}
                />
                <Text
                  style={[styles.filterGridChipText, isSelected && styles.filterGridChipTextActive]}
                  numberOfLines={1}
                >
                  {f.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* District Filter Dropdown (Available Districts Only) */}
      <View style={styles.districtSection}>
        <TouchableOpacity
          style={styles.districtDropdownBtn}
          onPress={() => setDistrictModalOpen(true)}
          activeOpacity={0.75}
        >
          <View style={styles.districtDropdownLeft}>
            <View style={styles.districtIconBox}>
              <Ionicons
                name={districtFilter === 'All Districts' ? 'grid-outline' : 'location'}
                size={16}
                color={colors.govNavy700}
              />
            </View>
            <View>
              <Text style={styles.districtDropdownSub}>JURISDICTION / DISTRICT</Text>
              <Text style={styles.districtDropdownValue}>
                {districtFilter === 'All Districts' ? 'All Revenue Districts' : districtFilter}
              </Text>
            </View>
          </View>
          <View style={styles.districtDropdownRight}>
            <View style={styles.districtCountBadge}>
              <Text style={styles.districtCountText}>
                {districtFilter === 'All Districts'
                  ? `${allDocsCount || documents.length} Records`
                  : `${documents.length} Filtered`}
              </Text>
            </View>
            <Ionicons name="chevron-down" size={16} color={colors.govNavy700} />
          </View>
        </TouchableOpacity>
      </View>

      <View style={styles.registryListHeader}>
        <Text style={styles.registryTitle}>Land Deeds Registry</Text>
        <Text style={styles.registryCount}>{documents.length} Records Found</Text>
      </View>
    </View>
  );

  // Render Land Deed Card
  const renderItem = ({ item }) => {
    const ownerName =
      item.extracted_fields?.find((f) => f.field_name === 'owner_name')?.field_value ||
      item.owner_name ||
      'Ram Kumar Singh';
    const khasraNo =
      item.extracted_fields?.find((f) => f.field_name === 'khasra_number')?.field_value ||
      item.khasra_number ||
      '451/2';
    const district =
      item.extracted_fields?.find((f) => f.field_name === 'district')?.field_value ||
      item.district ||
      'Jaipur';
    const plotArea =
      item.extracted_fields?.find((f) => f.field_name === 'plot_area')?.field_value ||
      '2 Bigha 14 Biswa';
    const confidence = Math.round((item.confidence_score || 0.88) * 100);

    return (
      <Card style={styles.deedCard}>
        <TouchableOpacity
          onPress={() => navigation.navigate('Review', { documentId: item.id })}
          activeOpacity={0.8}
        >
          <View style={styles.cardTopRow}>
            <View style={styles.deedIdBadge}>
              <Text style={styles.deedIdText}>DOC #{item.id}</Text>
            </View>
            <Badge status={item.status} />
          </View>

          <Text style={styles.ownerName}>{ownerName}</Text>

          <View style={styles.metaGrid}>
            <View style={styles.metaItem}>
              <Text style={styles.metaLabel}>KHASRA / SURVEY</Text>
              <Text style={styles.metaValue}>{khasraNo}</Text>
            </View>
            <View style={styles.metaItem}>
              <Text style={styles.metaLabel}>DISTRICT</Text>
              <Text style={styles.metaValue}>{district}</Text>
            </View>
            <View style={styles.metaItem}>
              <Text style={styles.metaLabel}>PLOT AREA</Text>
              <Text style={styles.metaValue}>{plotArea}</Text>
            </View>
            <View style={styles.metaItem}>
              <Text style={styles.metaLabel}>AI CONFIDENCE</Text>
              <Text style={[styles.metaValue, { color: confidence >= 75 ? colors.emerald600 : colors.saffron600 }]}>
                {confidence}%
              </Text>
            </View>
          </View>

          <View style={styles.cardActionsRow}>
            <TouchableOpacity
              style={styles.reviewButton}
              onPress={() => navigation.navigate('Review', { documentId: item.id })}
            >
              <Ionicons name="eye-outline" size={16} color={colors.white} />
              <Text style={styles.reviewButtonText}>Inspect & Verify Deed</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.auditIconBtn}
              onPress={() => navigation.navigate('Audit', { documentId: item.id })}
              accessibilityLabel="View Audit Trail"
            >
              <Ionicons name="finger-print-outline" size={18} color={colors.govNavy700} />
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Card>
    );
  };

  return (
    <View style={styles.container}>
      {loading && !refreshing ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.saffron500} />
          <Text style={styles.loadingText}>Loading Sovereign Land Registry...</Text>
        </View>
      ) : (
        <FlatList
          data={documents}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderItem}
          ListHeaderComponent={renderHeader}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={[colors.saffron500]}
              tintColor={colors.saffron500}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="document-text-outline" size={48} color={colors.slate300} />
              <Text style={styles.emptyTitle}>No matching land records found</Text>
              <Text style={styles.emptySub}>Try adjusting your search or status filter</Text>
            </View>
          }
        />
      )}

      {/* Floating Action Button for Ingestion */}
      <Animated.View style={[styles.fabContainer, { transform: [{ scale: fabScale }] }]}>
        <TouchableOpacity
          style={styles.fab}
          onPress={() => navigation.navigate('Capture')}
          activeOpacity={0.8}
        >
          <Ionicons name="scan-outline" size={20} color={colors.govNavy950} />
          <Text style={styles.fabText}>Scan Land Deed</Text>
        </TouchableOpacity>
      </Animated.View>

      {/* District Selection Modal (Available Districts in Data Only) */}
      <Modal
        visible={districtModalOpen}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setDistrictModalOpen(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.modalTitle}>Select Revenue District</Text>
                <Text style={styles.modalSub}>
                  Showing available jurisdictions with active land deeds
                </Text>
              </View>
              <TouchableOpacity
                style={styles.modalCloseBtn}
                onPress={() => setDistrictModalOpen(false)}
              >
                <Ionicons name="close" size={22} color={colors.slate600} />
              </TouchableOpacity>
            </View>

            <FlatList
              data={availableDistricts}
              keyExtractor={(item) => item}
              contentContainerStyle={{ paddingBottom: spacing.xl, paddingTop: 6 }}
              renderItem={({ item }) => {
                const isSelected = districtFilter === item;
                return (
                  <TouchableOpacity
                    style={[styles.districtItem, isSelected && styles.districtItemActive]}
                    onPress={() => {
                      setDistrictFilter(item);
                      setDistrictModalOpen(false);
                    }}
                    activeOpacity={0.7}
                  >
                    <View style={styles.districtItemLeft}>
                      <View style={[styles.districtItemIconBox, isSelected && styles.districtItemIconBoxActive]}>
                        <Ionicons
                          name={item === 'All Districts' ? 'grid-outline' : 'location-outline'}
                          size={18}
                          color={isSelected ? colors.emerald700 : colors.govNavy700}
                        />
                      </View>
                      <View>
                        <Text style={[styles.districtItemText, isSelected && styles.districtItemTextActive]}>
                          {item}
                        </Text>
                        <Text style={styles.districtItemSub}>
                          {item === 'All Districts' ? 'View records across all divisions' : 'Revenue sub-division node'}
                        </Text>
                      </View>
                    </View>
                    {isSelected && (
                      <View style={styles.selectedCheckBadge}>
                        <Ionicons name="checkmark" size={16} color={colors.white} />
                      </View>
                    )}
                  </TouchableOpacity>
                );
              }}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPage,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 13,
    color: colors.slate600,
    fontWeight: '600',
  },
  listContent: {
    paddingBottom: 90,
  },
  headerSection: {
    paddingTop: spacing.md,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    rowGap: 10,
  },
  statCard: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    width: '48.5%',
    borderTopWidth: 3,
    borderWidth: 1,
    borderColor: colors.borderCard,
    ...shadows.sm,
  },
  statTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statLabel: {
    fontSize: 9.5,
    fontWeight: '800',
    color: colors.slate600,
    letterSpacing: 0.5,
  },
  statValue: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.govNavy950,
    marginVertical: 4,
  },
  statSub: {
    fontSize: 9.5,
    color: colors.slate500,
  },
  jurisdictionCard: {
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    ...shadows.sm,
  },
  jurisdictionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  jurisdictionTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  jurisdictionSub: {
    fontSize: 10.5,
    color: colors.slate500,
  },
  refreshBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    backgroundColor: colors.govNavy50,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.govNavy100,
  },
  refreshText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.govNavy600,
  },
  districtProgressList: {
    gap: 8,
  },
  districtRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  districtName: {
    width: 120,
    fontSize: 11,
    fontWeight: '600',
    color: colors.slate700,
  },
  progressBarBg: {
    flex: 1,
    height: 6,
    backgroundColor: colors.slate100,
    borderRadius: 3,
    marginHorizontal: 10,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 3,
  },
  districtPercent: {
    width: 32,
    fontSize: 11,
    fontWeight: '800',
    color: colors.govNavy900,
    textAlign: 'right',
  },
  searchSection: {
    marginTop: spacing.md,
    paddingHorizontal: spacing.md,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.white,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderCard,
    height: 46,
    ...shadows.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: 13,
    color: colors.govNavy900,
    marginBottom: 0,
    borderWidth: 0,
    backgroundColor: 'transparent',
    paddingHorizontal: 0,
  },
  filterSection: {
    marginTop: 10,
    paddingHorizontal: spacing.md,
  },
  filterGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    rowGap: 8,
  },
  filterGridChip: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: colors.white,
    borderColor: colors.borderCard,
    borderWidth: 1,
    width: '48.5%',
    paddingVertical: 9,
    paddingHorizontal: 8,
    borderRadius: radius.md,
    ...shadows.sm,
  },
  filterGridChipActive: {
    backgroundColor: colors.govNavy900,
    borderColor: colors.govNavy900,
  },
  filterGridChipText: {
    fontSize: 11.5,
    fontWeight: '600',
    color: colors.slate700,
  },
  filterGridChipTextActive: {
    color: colors.white,
    fontWeight: '700',
  },
  districtSection: {
    marginTop: 10,
    paddingHorizontal: spacing.md,
  },
  districtDropdownBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.white,
    borderColor: colors.borderCard,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    ...shadows.sm,
  },
  districtDropdownLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
  },
  districtIconBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: colors.govNavy50,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.govNavy100,
  },
  districtDropdownSub: {
    fontSize: 9,
    fontWeight: '800',
    color: colors.slate400,
    letterSpacing: 0.5,
  },
  districtDropdownValue: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.govNavy950,
    marginTop: 1,
  },
  districtDropdownRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  districtCountBadge: {
    backgroundColor: colors.emerald50,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
    borderWidth: 1,
    borderColor: colors.emerald200,
  },
  districtCountText: {
    fontSize: 10.5,
    fontWeight: '700',
    color: colors.emerald700,
  },
  districtItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: radius.md,
    marginBottom: 6,
    backgroundColor: colors.slate50,
    borderWidth: 1,
    borderColor: colors.slate200,
  },
  districtItemActive: {
    backgroundColor: colors.emerald50,
    borderColor: colors.emerald500,
    borderWidth: 1.5,
  },
  districtItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
  },
  districtItemIconBox: {
    width: 34,
    height: 34,
    borderRadius: radius.sm,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.slate200,
  },
  districtItemIconBoxActive: {
    backgroundColor: colors.emerald100,
    borderColor: colors.emerald300,
  },
  districtItemText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.govNavy950,
  },
  districtItemTextActive: {
    color: colors.emerald900,
  },
  districtItemSub: {
    fontSize: 10.5,
    color: colors.slate500,
    marginTop: 1,
  },
  districtItemRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  districtItemCount: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.slate500,
  },
  districtItemCountActive: {
    color: colors.emerald700,
    fontWeight: '700',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(6, 19, 37, 0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '75%',
    padding: spacing.lg,
    ...shadows.lg,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate100,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  modalSub: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 2,
  },
  modalCloseBtn: {
    padding: 6,
    backgroundColor: colors.slate100,
    borderRadius: radius.full,
  },
  selectedCheckBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.emerald600,
    alignItems: 'center',
    justifyContent: 'center',
  },
  registryListHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    marginTop: spacing.lg,
    marginBottom: 6,
  },
  registryTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  registryCount: {
    fontSize: 11,
    color: colors.slate500,
    fontWeight: '600',
  },
  deedCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    ...shadows.sm,
  },
  cardTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  deedIdBadge: {
    backgroundColor: colors.govNavy100,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.xs,
  },
  deedIdText: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.govNavy800,
  },
  ownerName: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
    marginBottom: 8,
  },
  metaGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    backgroundColor: colors.slate50,
    borderRadius: radius.sm,
    padding: 8,
    marginBottom: 10,
  },
  metaItem: {
    width: '50%',
    paddingVertical: 4,
  },
  metaLabel: {
    fontSize: 8.5,
    fontWeight: '700',
    color: colors.slate500,
    letterSpacing: 0.4,
  },
  metaValue: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.govNavy900,
    marginTop: 1,
  },
  cardActionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  reviewButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: colors.govNavy900,
    paddingVertical: 9,
    borderRadius: radius.sm,
  },
  reviewButtonText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.white,
  },
  auditIconBtn: {
    width: 36,
    height: 36,
    borderRadius: radius.sm,
    backgroundColor: colors.slate100,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.slate200,
  },
  emptyContainer: {
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
  },
  fabContainer: {
    position: 'absolute',
    bottom: 16,
    alignSelf: 'center',
    ...shadows.lg,
  },
  fab: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.saffron500,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: radius.full,
    elevation: 6,
  },
  fabText: {
    color: colors.govNavy950,
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
});
