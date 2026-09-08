import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { documentsApi } from '../api/client';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Input from '../components/common/Input';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing } from '../theme/theme';

const STATUS_FILTERS = [
  { id: 'all', label: 'All Statuses' },
  { id: 'needs_review', label: 'Needs Review' },
  { id: 'verified', label: 'Verified' },
  { id: 'processing', label: 'Processing' },
];

const DISTRICT_FILTERS = [
  'All Districts',
  'Patna',
  'Gaya',
  'Muzaffarpur',
  'Bhagalpur',
  'Darbhanga',
  'Purnia',
  'Rohtas',
  'Saran',
];

export default function RegistryScreen({ navigation }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [districtFilter, setDistrictFilter] = useState('All Districts');

  const fetchDocuments = useCallback(async () => {
    try {
      setError(null);
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (districtFilter !== 'All Districts') params.district = districtFilter;
      if (search.trim()) params.search = search.trim();

      const res = await documentsApi.list(params);
      setDocuments(res.items || res || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch land records registry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter, districtFilter, search]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchDocuments();
  };

  const renderItem = ({ item }) => (
    <Card style={styles.recordCard}>
      <View style={styles.cardHeader}>
        <View style={{ flex: 1, marginRight: spacing.xs }}>
          <Text style={styles.docTitle}>{item.title || `Land Record #${item.id}`}</Text>
          <Text style={styles.docSub}>
            ID #{item.id} • District: {item.district || 'N/A'}
          </Text>
        </View>
        <Badge status={item.status} />
      </View>

      <View style={styles.metaRow}>
        <Text style={styles.metaText}>
          📅 Ingested:{' '}
          {item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent'}
        </Text>
        <Text style={styles.metaText}>
          👤 {item.uploaded_by_user?.username || 'Field Officer'}
        </Text>
      </View>

      <View style={styles.cardActions}>
        <Button
          title="Audit Trail"
          onPress={() => navigation.navigate('Audit', { documentId: item.id })}
          variant="outline"
          style={{ flex: 1, marginRight: spacing.xs, minHeight: 38 }}
          textStyle={{ fontSize: typography.sizes.xs }}
        />
        <Button
          title="Review & Verify"
          onPress={() => navigation.navigate('Review', { documentId: item.id })}
          variant="saffron"
          style={{ flex: 1, marginLeft: spacing.xs, minHeight: 38 }}
          textStyle={{ fontSize: typography.sizes.xs }}
        />
      </View>
    </Card>
  );

  return (
    <View style={styles.container}>
      <View style={styles.filterSection}>
        <Text style={styles.screenTitle}>Sovereign Land Registry</Text>
        <Text style={styles.screenSub}>Search and verify official state land records</Text>

        <Input
          value={search}
          onChangeText={setSearch}
          placeholder="🔍 Search owner name, Khasra, title or ID..."
          style={{ marginBottom: spacing.xs }}
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
              style={[
                styles.chip,
                statusFilter === item.id && styles.chipActive,
              ]}
              onPress={() => setStatusFilter(item.id)}
            >
              <Text
                style={[
                  styles.chipText,
                  statusFilter === item.id && styles.chipTextActive,
                ]}
              >
                {item.label}
              </Text>
            </TouchableOpacity>
          )}
        />

        {/* District Filter Chips */}
        <FlatList
          horizontal
          data={DISTRICT_FILTERS}
          keyExtractor={(item) => item}
          showsHorizontalScrollIndicator={false}
          style={styles.chipScroll}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[
                styles.chip,
                districtFilter === item && styles.chipActiveNavy,
              ]}
              onPress={() => setDistrictFilter(item)}
            >
              <Text
                style={[
                  styles.chipText,
                  districtFilter === item && styles.chipTextActive,
                ]}
              >
                {item}
              </Text>
            </TouchableOpacity>
          )}
        />
      </View>

      {error ? (
        <Card style={styles.errorCard}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
          <Button title="Retry" onPress={fetchDocuments} variant="outline" style={{ marginTop: spacing.sm }} />
        </Card>
      ) : null}

      {loading && !refreshing ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.govNavy600} />
          <Text style={styles.loadingText}>Fetching registry records...</Text>
        </View>
      ) : (
        <FlatList
          data={documents}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
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
              <Text style={styles.emptyTitle}>No matching land records found.</Text>
              <Text style={styles.emptySub}>
                Try adjusting your search query or status/district filters.
              </Text>
            </Card>
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
  filterSection: {
    backgroundColor: colors.white,
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderCard,
  },
  screenTitle: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  screenSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    marginBottom: spacing.sm,
  },
  chipScroll: {
    marginTop: 4,
    marginBottom: 4,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: radius.full,
    backgroundColor: colors.slate100,
    borderColor: colors.slate300,
    borderWidth: 1,
    marginRight: 6,
  },
  chipActive: {
    backgroundColor: colors.saffron600,
    borderColor: colors.saffron600,
  },
  chipActiveNavy: {
    backgroundColor: colors.govNavy900,
    borderColor: colors.govNavy900,
  },
  chipText: {
    fontSize: typography.sizes.xs,
    color: colors.slate700,
    fontWeight: typography.weights.medium,
  },
  chipTextActive: {
    color: colors.white,
    fontWeight: typography.weights.bold,
  },
  listContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  loadingText: {
    marginTop: spacing.md,
    color: colors.slate600,
    fontSize: typography.sizes.sm,
  },
  errorCard: {
    margin: spacing.md,
    backgroundColor: colors.rose50,
    borderColor: colors.rose600,
  },
  errorText: {
    color: colors.rose800,
    fontSize: typography.sizes.sm,
  },
  recordCard: {
    marginBottom: spacing.sm,
    padding: spacing.md,
  },
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
  docSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.xs,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.slate100,
    marginVertical: spacing.xs,
  },
  metaText: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
  },
  cardActions: {
    flexDirection: 'row',
    marginTop: spacing.xs,
  },
  emptyCard: {
    alignItems: 'center',
    padding: spacing.xl,
    marginTop: spacing.lg,
  },
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
  },
});
