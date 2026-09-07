import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { dashboardApi } from '../api/client';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Badge from '../components/common/Badge';
import { colors, radius, typography, spacing, shadows } from '../theme/theme';

export default function DashboardScreen({ navigation }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      setError(null);
      const data = await dashboardApi.getStats();
      setStats(data);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard statistics');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchStats();
  };

  if (loading && !refreshing) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.govNavy600} />
        <Text style={styles.loadingText}>Fetching Sovereign Registry Analytics...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.scrollContent}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          colors={[colors.govNavy600]}
          tintColor={colors.govNavy600}
        />
      }
    >
      <View style={styles.bannerContainer}>
        <Text style={styles.bannerTitle}>Field Verification Dashboard</Text>
        <Text style={styles.bannerSub}>Real-time oversight for land record ingestion & audit</Text>
      </View>

      {error ? (
        <Card style={styles.errorCard}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
          <Button title="Retry Loading" onPress={fetchStats} variant="outline" style={{ marginTop: spacing.sm }} />
        </Card>
      ) : null}

      {/* Quick Action Bar */}
      <View style={styles.quickActionsRow}>
        <TouchableOpacity
          activeOpacity={0.8}
          style={[styles.actionBtn, { backgroundColor: colors.saffron600 }]}
          onPress={() => navigation.navigate('Capture')}
        >
          <Text style={styles.actionIcon}>📷</Text>
          <Text style={styles.actionText}>Scan Land Record</Text>
        </TouchableOpacity>
        <TouchableOpacity
          activeOpacity={0.8}
          style={[styles.actionBtn, { backgroundColor: colors.govNavy800 }]}
          onPress={() => navigation.navigate('Registry')}
        >
          <Text style={styles.actionIcon}>📁</Text>
          <Text style={styles.actionText}>Land Registry</Text>
        </TouchableOpacity>
      </View>

      {/* Main KPI Stats Grid */}
      <View style={styles.statsGrid}>
        <Card style={styles.statCard}>
          <Text style={styles.statIcon}>📄</Text>
          <Text style={styles.statNumber}>{stats?.total_documents || 0}</Text>
          <Text style={styles.statLabel}>Total Ingested</Text>
        </Card>

        <Card style={styles.statCard}>
          <Text style={styles.statIcon}>✅</Text>
          <Text style={[styles.statNumber, { color: colors.emerald700 }]}>
            {stats?.verified || 0}
          </Text>
          <Text style={styles.statLabel}>Verified Records</Text>
        </Card>

        <Card style={styles.statCard}>
          <Text style={styles.statIcon}>⏳</Text>
          <Text style={[styles.statNumber, { color: colors.saffron700 }]}>
            {stats?.pending_review || 0}
          </Text>
          <Text style={styles.statLabel}>Needs Review</Text>
        </Card>

        <Card style={styles.statCard}>
          <Text style={styles.statIcon}>🚩</Text>
          <Text style={[styles.statNumber, { color: colors.rose700 }]}>
            {stats?.flagged_field_count || 0}
          </Text>
          <Text style={styles.statLabel}>Flagged Fields</Text>
        </Card>
      </View>

      {/* Accuracy & Quality Card */}
      <Card style={styles.qualityCard}>
        <View style={styles.qualityHeader}>
          <View>
            <Text style={styles.qualityTitle}>Extraction Quality Index</Text>
            <Text style={styles.qualitySub}>Mean confidence across OCR & LLM extracted fields</Text>
          </View>
          <Text style={styles.qualityScore}>
            {stats?.avg_confidence != null
              ? `${(stats.avg_confidence * 100).toFixed(1)}%`
              : 'N/A'}
          </Text>
        </View>
        <View style={styles.progressTrack}>
          <View
            style={[
              styles.progressBar,
              {
                width: `${Math.min(100, Math.max(0, (stats?.avg_confidence || 0) * 100))}%`,
                backgroundColor:
                  (stats?.avg_confidence || 0) > 0.85
                    ? colors.emerald600
                    : (stats?.avg_confidence || 0) > 0.7
                    ? colors.saffron600
                    : colors.rose600,
              },
            ]}
          />
        </View>
        <View style={styles.qualityFooter}>
          <Text style={styles.qualityFooterText}>
            Total Attributes Evaluated: {stats?.total_fields || 0}
          </Text>
        </View>
      </Card>

      {/* District Breakdown */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>District Performance Breakdown</Text>
        <Text style={styles.sectionSub}>State revenue district distribution</Text>
      </View>

      {stats?.district_breakdown && stats.district_breakdown.length > 0 ? (
        stats.district_breakdown.map((item, idx) => (
          <Card key={idx} style={styles.districtCard}>
            <View style={styles.districtRow}>
              <View>
                <Text style={styles.districtName}>
                  📍 {item.district || 'Unassigned District'}
                </Text>
                <Text style={styles.districtTotal}>
                  {item.total_documents} {item.total_documents === 1 ? 'document' : 'documents'} total
                </Text>
              </View>
              <View style={styles.districtBadges}>
                <Badge status="verified" label={`${item.verified} V`} style={{ marginRight: 4 }} />
                <Badge status="needs_review" label={`${item.needs_review} R`} />
              </View>
            </View>
          </Card>
        ))
      ) : (
        <Card style={styles.emptyCard}>
          <Text style={styles.emptyText}>No district records ingested yet.</Text>
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPage,
  },
  scrollContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.bgPage,
    padding: spacing.xl,
  },
  loadingText: {
    marginTop: spacing.md,
    color: colors.slate600,
    fontSize: typography.sizes.sm,
  },
  bannerContainer: {
    marginBottom: spacing.md,
  },
  bannerTitle: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  bannerSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    marginTop: 2,
  },
  errorCard: {
    backgroundColor: colors.rose50,
    borderColor: colors.rose600,
  },
  errorText: {
    color: colors.rose800,
    fontSize: typography.sizes.sm,
  },
  quickActionsRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    ...shadows.sm,
  },
  actionIcon: {
    fontSize: 18,
    marginRight: 8,
  },
  actionText: {
    color: colors.white,
    fontWeight: typography.weights.bold,
    fontSize: typography.sizes.sm,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    marginBottom: spacing.xs,
  },
  statCard: {
    width: '47.5%',
    alignItems: 'center',
    paddingVertical: spacing.md,
  },
  statIcon: {
    fontSize: 22,
    marginBottom: 4,
  },
  statNumber: {
    fontSize: typography.sizes.xxl,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  statLabel: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    marginTop: 2,
    fontWeight: typography.weights.medium,
  },
  qualityCard: {
    marginTop: spacing.xs,
    marginBottom: spacing.md,
  },
  qualityHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
  },
  qualityTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  qualitySub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
  },
  qualityScore: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.govNavy700,
  },
  progressTrack: {
    height: 8,
    backgroundColor: colors.slate200,
    borderRadius: radius.full,
    overflow: 'hidden',
    marginBottom: spacing.xs,
  },
  progressBar: {
    height: '100%',
    borderRadius: radius.full,
  },
  qualityFooter: {
    alignItems: 'flex-end',
  },
  qualityFooterText: {
    fontSize: 10,
    color: colors.slate500,
  },
  sectionHeader: {
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  sectionTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  sectionSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginBottom: spacing.xs,
  },
  districtCard: {
    marginBottom: spacing.xs,
    paddingVertical: spacing.md,
  },
  districtRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  districtName: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  districtTotal: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  districtBadges: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  emptyCard: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  emptyText: {
    color: colors.slate500,
    fontSize: typography.sizes.sm,
  },
});
