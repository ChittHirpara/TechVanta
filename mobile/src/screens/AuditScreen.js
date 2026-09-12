import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { documentsApi } from '../api/client';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing } from '../theme/theme';

export default function AuditScreen({ route, navigation }) {
  const { documentId } = route.params || {};

  const [document, setDocument] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [integrity, setIntegrity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const fetchAuditData = useCallback(async () => {
    if (!documentId) return;
    try {
      const [docData, auditData, integrityData] = await Promise.all([
        documentsApi.get(documentId).catch(() => null),
        documentsApi.getAudit(documentId).catch(() => []),
        documentsApi.getIntegrity(documentId).catch(() => null),
      ]);
      setError(null);

      setDocument(docData);
      setAuditLogs(auditData || []);
      setIntegrity(integrityData);
    } catch (err) {
      setError(err.message || 'Failed to fetch audit log trail.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchAuditData();
  }, [fetchAuditData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchAuditData();
  };

  const getActionColor = (action) => {
    const act = (action || '').toUpperCase();
    if (act.includes('VERIF')) return colors.emerald700;
    if (act.includes('PATCH') || act.includes('EDIT')) return colors.saffron600;
    if (act.includes('UPLOAD') || act.includes('INGEST')) return colors.govNavy600;
    if (act.includes('ERR') || act.includes('FAIL')) return colors.rose600;
    return colors.slate700;
  };

  if (loading && !refreshing) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.govNavy600} />
        <Text style={styles.loadingText}>Fetching Cryptographic Audit Trail...</Text>
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
      {/* Header Info */}
      <Card style={styles.headerCard}>
        <Text style={styles.headerTitle}>
          Audit Trail: {document?.title || `Document #${documentId}`}
        </Text>
        <Text style={styles.headerSub}>
          Immutable event log for legal verification & sovereign compliance
        </Text>

        {integrity?.sha256 || document?.sha256_hash ? (
          <View style={styles.hashBox}>
            <Text style={styles.hashLabel}>🔒 SHA-256 Integrity Seal:</Text>
            <Text style={styles.hashValue}>
              {integrity?.sha256 || document?.sha256_hash}
            </Text>
          </View>
        ) : null}
      </Card>

      {error ? (
        <Card style={styles.errorCard}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
          <Button title="Retry Loading" onPress={fetchAuditData} variant="outline" style={{ marginTop: spacing.sm }} />
        </Card>
      ) : null}

      {/* Audit Timeline Section */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>
          Verification Chronology ({auditLogs.length} events)
        </Text>
      </View>

      {auditLogs.length > 0 ? (
        auditLogs.map((log, index) => (
          <View key={log.id || index} style={styles.timelineItem}>
            <View style={styles.timelineLeft}>
              <View
                style={[
                  styles.timelineDot,
                  { backgroundColor: getActionColor(log.action) },
                ]}
              />
              {index < auditLogs.length - 1 ? <View style={styles.timelineLine} /> : null}
            </View>

            <Card style={styles.timelineCard}>
              <View style={styles.logHeader}>
                <View
                  style={[
                    styles.actionBadge,
                    { backgroundColor: `${getActionColor(log.action)}15` },
                  ]}
                >
                  <Text
                    style={[
                      styles.actionText,
                      { color: getActionColor(log.action) },
                    ]}
                  >
                    {(log.action || 'EVENT').toUpperCase()}
                  </Text>
                </View>
                <Text style={styles.logTime}>
                  {log.created_at || log.timestamp
                    ? new Date(log.created_at || log.timestamp).toLocaleString()
                    : 'Recent'}
                </Text>
              </View>

              <Text style={styles.logUser}>
                👤 Performed by: {log.user?.full_name || log.user?.username || log.performed_by || 'System Pipeline'}
                {log.user?.role ? ` (${log.user.role})` : ''}
              </Text>

              {log.details || log.description ? (
                <View style={styles.detailsBox}>
                  <Text style={styles.detailsText}>
                    {typeof log.details === 'object'
                      ? JSON.stringify(log.details, null, 2)
                      : log.details || log.description}
                  </Text>
                </View>
              ) : null}
            </Card>
          </View>
        ))
      ) : (
        <Card style={styles.emptyCard}>
          <Text style={styles.emptyText}>No audit entries recorded for this document.</Text>
        </Card>
      )}

      <Button
        title="Back to Document Review"
        onPress={() => navigation.navigate('Review', { documentId })}
        variant="outline"
        style={{ marginTop: spacing.md }}
      />
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
  headerCard: {
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  headerTitle: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  headerSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  hashBox: {
    marginTop: spacing.md,
    padding: spacing.sm,
    backgroundColor: colors.slate950,
    borderRadius: radius.sm,
  },
  hashLabel: {
    color: colors.saffron500,
    fontSize: 10,
    fontWeight: typography.weights.bold,
  },
  hashValue: {
    fontFamily: typography.fontFamily.mono,
    color: colors.slate200,
    fontSize: 11,
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
  sectionHeader: {
    marginBottom: spacing.xs,
  },
  sectionTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  timelineItem: {
    flexDirection: 'row',
    marginBottom: spacing.xs,
  },
  timelineLeft: {
    width: 24,
    alignItems: 'center',
    paddingTop: 16,
  },
  timelineDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  timelineLine: {
    flex: 1,
    width: 2,
    backgroundColor: colors.slate300,
    marginTop: 4,
  },
  timelineCard: {
    flex: 1,
    marginLeft: spacing.xs,
    padding: spacing.md,
  },
  logHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  actionBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.sm,
  },
  actionText: {
    fontSize: 10,
    fontWeight: typography.weights.bold,
    letterSpacing: 0.5,
  },
  logTime: {
    fontSize: 10,
    color: colors.slate500,
  },
  logUser: {
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.semibold,
    color: colors.slate700,
    marginBottom: spacing.xs,
  },
  detailsBox: {
    backgroundColor: colors.slate100,
    borderRadius: radius.xs,
    padding: spacing.sm,
    marginTop: spacing.xs,
  },
  detailsText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: 11,
    color: colors.slate800,
  },
  emptyCard: {
    alignItems: 'center',
    padding: spacing.xl,
  },
  emptyText: {
    color: colors.slate500,
    fontSize: typography.sizes.sm,
  },
});
