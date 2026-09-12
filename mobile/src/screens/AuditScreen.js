import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { documentsApi } from '../api/client';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing, shadows } from '../theme/theme';

export default function AuditScreen({ route, navigation }) {
  const { documentId: paramDocId } = route.params || {};

  const [documentList, setDocumentList] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(paramDocId || null);
  const [document, setDocument] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [integrity, setIntegrity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // If no documentId was passed, load available documents first
  useEffect(() => {
    async function loadDocs() {
      try {
        const res = await documentsApi.list({ pageSize: 10 });
        const items = res.items || res || [];
        setDocumentList(items);
        if (!selectedDocId && items.length > 0) {
          setSelectedDocId(items[0].id);
        }
      } catch (_) {}
    }
    loadDocs();
  }, []);

  const fetchAuditData = useCallback(async () => {
    const docId = selectedDocId || paramDocId;
    if (!docId) {
      setLoading(false);
      setRefreshing(false);
      return;
    }

    try {
      setLoading(true);
      const [docData, auditData, integrityData] = await Promise.all([
        documentsApi.get(docId).catch(() => null),
        documentsApi.getAudit(docId).catch(() => []),
        documentsApi.getIntegrity(docId).catch(() => null),
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
  }, [selectedDocId, paramDocId]);

  useEffect(() => {
    fetchAuditData();
  }, [fetchAuditData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchAuditData();
  };

  const getActionMeta = (action) => {
    const act = (action || '').toUpperCase();
    if (act.includes('VERIF')) {
      return { icon: 'checkmark-done-circle', color: colors.emerald600, bg: 'rgba(16, 185, 129, 0.12)', label: 'VERIFIED & SEALED' };
    }
    if (act.includes('PATCH') || act.includes('EDIT')) {
      return { icon: 'create-outline', color: colors.saffron600, bg: 'rgba(245, 158, 11, 0.12)', label: 'OFFICER CORRECTION' };
    }
    if (act.includes('UPLOAD') || act.includes('INGEST')) {
      return { icon: 'cloud-upload-outline', color: colors.govNavy600, bg: 'rgba(37, 99, 235, 0.12)', label: 'DOCUMENT INGESTED' };
    }
    if (act.includes('PIPELINE_STARTED')) {
      return { icon: 'cog-outline', color: colors.govNavy700, bg: 'rgba(19, 52, 88, 0.12)', label: 'AI PIPELINE STARTED' };
    }
    if (act.includes('ERR') || act.includes('FAIL')) {
      return { icon: 'alert-circle-outline', color: colors.rose600, bg: 'rgba(220, 38, 38, 0.12)', label: 'PIPELINE LOG' };
    }
    return { icon: 'time-outline', color: colors.slate600, bg: colors.slate100, label: act || 'AUDIT EVENT' };
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.scrollContent}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          colors={[colors.saffron500]}
          tintColor={colors.saffron500}
        />
      }
    >
      {/* Top Sovereign Banner */}
      <Card style={styles.headerCard}>
        <View style={styles.headerTop}>
          <View style={styles.sealIcon}>
            <Ionicons name="shield-checkmark" size={24} color={colors.saffron500} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>
              {document?.title || (selectedDocId ? `Document #${selectedDocId}` : 'Legal Audit Ledger')}
            </Text>
            <Text style={styles.headerSub}>
              Immutable SHA-256 chain of custody for legal court compliance
            </Text>
          </View>
        </View>

        {/* SHA-256 Hash Display */}
        {(integrity?.sha256 || document?.sha256_hash) && (
          <View style={styles.hashBox}>
            <View style={styles.hashHeader}>
              <Ionicons name="lock-closed" size={12} color={colors.saffron600} />
              <Text style={styles.hashLabel}>CRYPTOGRAPHIC SHA-256 SEAL:</Text>
            </View>
            <Text style={styles.hashValue} numberOfLines={2}>
              {integrity?.sha256 || document?.sha256_hash}
            </Text>
          </View>
        )}
      </Card>

      {/* Document Selector Pills (if multiple available) */}
      {documentList.length > 1 && (
        <View style={styles.selectorSection}>
          <Text style={styles.selectorTitle}>SELECT DOCUMENT RECORD:</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.docPillList}>
            {documentList.map((doc) => {
              const isCurrent = doc.id === (selectedDocId || paramDocId);
              return (
                <TouchableOpacity
                  key={doc.id}
                  style={[styles.docPill, isCurrent && styles.docPillActive]}
                  onPress={() => setSelectedDocId(doc.id)}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.docPillText, isCurrent && styles.docPillTextActive]}>
                    Doc #{doc.id} • {doc.district || 'Jaipur'}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>
      )}

      {/* Audit Timeline Section */}
      <View style={styles.timelineHeader}>
        <Text style={styles.timelineTitle}>
          Verification Chronology ({auditLogs.length} Events)
        </Text>
        <Text style={styles.timelineSub}>Tamper-evident sovereign audit trail</Text>
      </View>

      {loading && !refreshing ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.saffron500} />
          <Text style={styles.loadingText}>Loading cryptographic audit events...</Text>
        </View>
      ) : auditLogs.length > 0 ? (
        <View style={styles.timelineWrapper}>
          {auditLogs.map((log, index) => {
            const meta = getActionMeta(log.action);
            const isLast = index === auditLogs.length - 1;

            return (
              <View key={log.id || index} style={styles.timelineItem}>
                <View style={styles.timelineLeft}>
                  <View style={[styles.timelineNode, { backgroundColor: meta.bg, borderColor: meta.color }]}>
                    <Ionicons name={meta.icon} size={14} color={meta.color} />
                  </View>
                  {!isLast && <View style={styles.timelineConnector} />}
                </View>

                <Card style={styles.timelineCard}>
                  <View style={styles.logTopRow}>
                    <View style={[styles.actionBadge, { backgroundColor: meta.bg }]}>
                      <Text style={[styles.actionBadgeText, { color: meta.color }]}>
                        {meta.label}
                      </Text>
                    </View>
                    <Text style={styles.logTimestamp}>
                      {log.created_at || log.timestamp
                        ? new Date(log.created_at || log.timestamp).toLocaleString()
                        : 'Recent'}
                    </Text>
                  </View>

                  <View style={styles.logUserRow}>
                    <Ionicons name="person-outline" size={12} color={colors.slate500} />
                    <Text style={styles.logUserText}>
                      Performed by: <Text style={{ fontWeight: '700', color: colors.govNavy900 }}>
                        {log.user?.full_name || log.user?.username || log.performed_by || 'System Pipeline'}
                      </Text>
                    </Text>
                  </View>

                  {/* Clean Formatted Details */}
                  {log.details ? (
                    <View style={styles.detailsContainer}>
                      {typeof log.details === 'object' ? (
                        Object.entries(log.details).map(([k, v]) => (
                          <View key={k} style={styles.detailRow}>
                            <Text style={styles.detailKey}>{k}:</Text>
                            <Text style={styles.detailVal}>
                              {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                            </Text>
                          </View>
                        ))
                      ) : (
                        <Text style={styles.detailRawText}>{String(log.details)}</Text>
                      )}
                    </View>
                  ) : null}
                </Card>
              </View>
            );
          })}
        </View>
      ) : (
        <Card style={styles.emptyCard}>
          <Ionicons name="shield-outline" size={36} color={colors.slate300} />
          <Text style={styles.emptyTitle}>No audit events for this record</Text>
          <Text style={styles.emptySub}>Actions performed on this document will appear here</Text>
        </Card>
      )}

      {selectedDocId && (
        <Button
          title="Inspect & Verify Document Fields"
          onPress={() => navigation.navigate('Review', { documentId: selectedDocId })}
          variant="saffron"
          style={{ marginTop: spacing.lg }}
        />
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
    paddingVertical: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 12,
    color: colors.slate600,
    fontWeight: '600',
  },
  headerCard: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    marginBottom: spacing.md,
    ...shadows.sm,
  },
  headerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  sealIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.govNavy950,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.saffron500,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  headerSub: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 2,
  },
  hashBox: {
    backgroundColor: colors.slate50,
    borderRadius: radius.sm,
    padding: 10,
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate200,
  },
  hashHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 3,
  },
  hashLabel: {
    fontSize: 9.5,
    fontWeight: '800',
    color: colors.saffron700,
    letterSpacing: 0.5,
  },
  hashValue: {
    fontSize: 10.5,
    color: colors.slate700,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    lineHeight: 14,
  },
  selectorSection: {
    marginBottom: spacing.md,
  },
  selectorTitle: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.slate500,
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  docPillList: {
    gap: 6,
  },
  docPill: {
    backgroundColor: colors.white,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.borderCard,
  },
  docPillActive: {
    backgroundColor: colors.govNavy900,
    borderColor: colors.govNavy900,
  },
  docPillText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.slate700,
  },
  docPillTextActive: {
    color: colors.white,
    fontWeight: '700',
  },
  timelineHeader: {
    marginBottom: spacing.sm,
    paddingHorizontal: 2,
  },
  timelineTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  timelineSub: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 1,
  },
  timelineWrapper: {
    paddingTop: 4,
  },
  timelineItem: {
    flexDirection: 'row',
    marginBottom: spacing.sm,
  },
  timelineLeft: {
    alignItems: 'center',
    width: 32,
    marginRight: 8,
  },
  timelineNode: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
  },
  timelineConnector: {
    width: 2,
    flex: 1,
    backgroundColor: colors.slate200,
    marginVertical: 4,
  },
  timelineCard: {
    flex: 1,
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    ...shadows.sm,
  },
  logTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  actionBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
  },
  actionBadgeText: {
    fontSize: 9.5,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  logTimestamp: {
    fontSize: 10,
    color: colors.slate400,
  },
  logUserRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 6,
  },
  logUserText: {
    fontSize: 11,
    color: colors.slate600,
  },
  detailsContainer: {
    backgroundColor: colors.slate50,
    borderRadius: radius.xs,
    padding: 8,
    borderWidth: 1,
    borderColor: colors.slate100,
  },
  detailRow: {
    flexDirection: 'row',
    marginBottom: 2,
  },
  detailKey: {
    fontSize: 10.5,
    fontWeight: '700',
    color: colors.slate600,
    width: 100,
  },
  detailVal: {
    fontSize: 10.5,
    color: colors.govNavy900,
    flex: 1,
    fontWeight: '500',
  },
  detailRawText: {
    fontSize: 10.5,
    color: colors.slate700,
  },
  emptyCard: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 30,
    backgroundColor: colors.white,
    borderRadius: radius.md,
  },
  emptyTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.slate600,
    marginTop: 8,
  },
  emptySub: {
    fontSize: 11,
    color: colors.slate400,
    marginTop: 2,
  },
});
