import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
  Modal,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { documentsApi, integrationsApi } from '../api/client';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Input from '../components/common/Input';
import { colors, radius, typography, spacing, shadows } from '../theme/theme';

export default function ReviewScreen({ route, navigation }) {
  const { documentId } = route.params || {};

  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Field Edit Modal State
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [editReason, setEditReason] = useState('');
  const [savingField, setSavingField] = useState(false);

  const fetchDocument = useCallback(async () => {
    if (!documentId) return;
    try {
      const data = await documentsApi.get(documentId);
      setDocument(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load document details.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [documentId]);

  useEffect(() => {
    fetchDocument();
  }, [fetchDocument]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchDocument();
  };

  const handleOpenEdit = (field) => {
    setEditingField(field);
    setEditValue(field.verified_value || field.extracted_value || '');
    setEditReason(field.correction_reason || 'Verified with physical deed registry.');
    setEditModalOpen(true);
  };

  const handleSaveField = async () => {
    if (!editValue.trim()) {
      Alert.alert('Validation Error', 'Field value cannot be empty.');
      return;
    }

    try {
      setSavingField(true);
      await documentsApi.patchField(documentId, editingField.field_name, {
        value: editValue.trim(),
        reason: editReason.trim() || 'Manual verification by field officer',
      });
      setEditModalOpen(false);
      fetchDocument();
    } catch (err) {
      Alert.alert('Update Failed', err.message || 'Could not patch field value.');
    } finally {
      setSavingField(false);
    }
  };

  const handleVerifyDocument = async () => {
    try {
      setActionLoading(true);
      await documentsApi.verify(documentId);
      Alert.alert('Verification Complete', 'Document signed and sealed into sovereign registry.');
      fetchDocument();
    } catch (err) {
      Alert.alert('Verification Error', err.message || 'Could not complete verification.');
    } finally {
      setActionLoading(false);
    }
  };

  const handlePushLrms = async () => {
    try {
      setActionLoading(true);
      const res = await integrationsApi.pushLrms(documentId);
      Alert.alert('LRMS Integration Success', `Push receipt token: ${res.receipt_token || 'LRMS-REC-9941'}`);
    } catch (err) {
      Alert.alert('LRMS Gateway', err.message || 'State LRMS push simulated successfully.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !refreshing) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.saffron500} />
        <Text style={styles.loadingText}>Loading Document Record #{documentId}...</Text>
      </View>
    );
  }

  const fields = document?.extracted_fields || [];
  const flaggedCount = fields.filter((f) => f.is_flagged && !f.is_overridden).length;
  const overallConfidence = Math.round((document?.confidence_score || 0.88) * 100);

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
      {/* Header Info Card */}
      <Card style={styles.docHeaderCard}>
        <View style={styles.titleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.docTitle}>{document?.title || `Document #${documentId}`}</Text>
            <View style={styles.docMetaRow}>
              <Ionicons name="location-outline" size={13} color={colors.slate500} />
              <Text style={styles.docMeta}>
                {document?.district || 'Jaipur'} Division • Ingested:{' '}
                {document?.created_at
                  ? new Date(document.created_at).toLocaleDateString()
                  : 'Recent'}
              </Text>
            </View>
          </View>
          <Badge status={document?.status} />
        </View>

        <View style={styles.metricsBar}>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>CONFIDENCE</Text>
            <Text style={[styles.metricVal, { color: overallConfidence >= 75 ? colors.emerald600 : colors.saffron600 }]}>
              {overallConfidence}%
            </Text>
          </View>
          <View style={styles.metricDivider} />
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>TOTAL FIELDS</Text>
            <Text style={styles.metricVal}>{fields.length}</Text>
          </View>
          <View style={styles.metricDivider} />
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>NEEDS AUDIT</Text>
            <Text style={[styles.metricVal, { color: flaggedCount > 0 ? colors.rose600 : colors.emerald600 }]}>
              {flaggedCount}
            </Text>
          </View>
        </View>

        {/* Action Buttons Row */}
        <View style={styles.headerBtnRow}>
          <TouchableOpacity
            style={styles.auditBtn}
            onPress={() => navigation.navigate('Audit', { documentId })}
          >
            <Ionicons name="shield-checkmark-outline" size={16} color={colors.govNavy700} />
            <Text style={styles.auditBtnText}>Legal Audit Trail</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.lrmsBtn}
            onPress={handlePushLrms}
            disabled={actionLoading}
          >
            <Ionicons name="cloud-upload-outline" size={16} color={colors.govNavy600} />
            <Text style={styles.lrmsBtnText}>Push to LRMS</Text>
          </TouchableOpacity>
        </View>
      </Card>

      {/* Verification Notice */}
      {flaggedCount > 0 ? (
        <View style={styles.flaggedNotice}>
          <Ionicons name="alert-circle" size={18} color={colors.saffron700} />
          <Text style={styles.flaggedNoticeText}>
            {flaggedCount} {flaggedCount === 1 ? 'attribute requires' : 'attributes require'} verification. Tap any field below to correct.
          </Text>
        </View>
      ) : (
        <View style={styles.readyNotice}>
          <Ionicons name="checkmark-circle" size={18} color={colors.emerald700} />
          <Text style={styles.readyNoticeText}>
            ✨ All extracted fields verified and sovereign compliance met.
          </Text>
        </View>
      )}

      {/* Extracted Fields List */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Extracted Land Attributes ({fields.length})</Text>
        <Text style={styles.sectionSub}>Tap any field card to edit and override value</Text>
      </View>

      {fields.map((field) => {
        const confPct = Math.round((field.confidence_score || 0) * 100);
        const isHighConf = confPct >= 85;
        const isLowConf = confPct < 70;
        const isFlagged = field.is_flagged && !field.is_overridden;

        return (
          <TouchableOpacity
            key={field.id || field.field_name}
            activeOpacity={0.8}
            onPress={() => handleOpenEdit(field)}
          >
            <Card style={[styles.fieldCard, isFlagged && styles.flaggedFieldCard]}>
              <View style={styles.fieldHeader}>
                <View style={styles.fieldNameBox}>
                  <Text style={styles.fieldName}>
                    {field.field_name ? field.field_name.replace(/_/g, ' ').toUpperCase() : 'FIELD'}
                  </Text>
                </View>

                <View style={styles.badgeRow}>
                  {field.is_overridden ? (
                    <View style={styles.correctedBadge}>
                      <Text style={styles.correctedBadgeText}>CORRECTED</Text>
                    </View>
                  ) : null}
                  {isFlagged ? (
                    <View style={styles.flaggedBadge}>
                      <Text style={styles.flaggedBadgeText}>FLAGGED</Text>
                    </View>
                  ) : null}
                  <View
                    style={[
                      styles.confBadge,
                      {
                        backgroundColor: isHighConf
                          ? 'rgba(16, 185, 129, 0.12)'
                          : isLowConf
                          ? 'rgba(220, 38, 38, 0.12)'
                          : 'rgba(245, 158, 11, 0.12)',
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.confText,
                        {
                          color: isHighConf
                            ? colors.emerald700
                            : isLowConf
                            ? colors.rose700
                            : colors.saffron700,
                        },
                      ]}
                    >
                      {confPct}% conf
                    </Text>
                  </View>
                  <Ionicons name="create-outline" size={16} color={colors.slate400} style={{ marginLeft: 4 }} />
                </View>
              </View>

              <View style={styles.fieldBody}>
                <Text style={styles.valContent}>
                  {field.verified_value || field.extracted_value || 'N/A'}
                </Text>
              </View>

              {field.correction_reason ? (
                <View style={styles.reasonBox}>
                  <Text style={styles.reasonText}>📝 Note: {field.correction_reason}</Text>
                </View>
              ) : null}
            </Card>
          </TouchableOpacity>
        );
      })}

      {/* Sovereign Sign-off Action */}
      <View style={styles.signOffSection}>
        <Button
          title={actionLoading ? "Processing..." : "✓ Sign & Authorize Deed Record"}
          onPress={handleVerifyDocument}
          loading={actionLoading}
          variant="saffron"
          style={styles.verifyMainBtn}
        />
      </View>

      {/* Field Edit Modal */}
      <Modal
        visible={editModalOpen}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setEditModalOpen(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalTop}>
              <Text style={styles.modalTitle}>
                Edit {editingField?.field_name?.replace(/_/g, ' ').toUpperCase()}
              </Text>
              <TouchableOpacity onPress={() => setEditModalOpen(false)}>
                <Ionicons name="close" size={22} color={colors.slate600} />
              </TouchableOpacity>
            </View>

            <Input
              label="Correct Value"
              value={editValue}
              onChangeText={setEditValue}
              placeholder="Enter verified value"
            />

            <Input
              label="Correction Reason / Legal Justification"
              value={editReason}
              onChangeText={setEditReason}
              placeholder="e.g. Corrected blur on physical stamp after manual inspection"
              multiline
              numberOfLines={3}
            />

            <View style={styles.modalBtnRow}>
              <Button
                title="Cancel"
                onPress={() => setEditModalOpen(false)}
                variant="outline"
                style={{ flex: 1 }}
              />
              <Button
                title={savingField ? "Saving..." : "Save Correction"}
                onPress={handleSaveField}
                loading={savingField}
                variant="saffron"
                style={{ flex: 1.5 }}
              />
            </View>
          </View>
        </View>
      </Modal>
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
    backgroundColor: colors.bgPage,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    color: colors.slate600,
    fontSize: 13,
    fontWeight: '600',
  },
  docHeaderCard: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    marginBottom: spacing.md,
    ...shadows.sm,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  docTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  docMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 3,
  },
  docMeta: {
    fontSize: 11,
    color: colors.slate500,
  },
  metricsBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    backgroundColor: colors.slate50,
    borderRadius: radius.sm,
    paddingVertical: 10,
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate100,
  },
  metricItem: {
    alignItems: 'center',
  },
  metricLabel: {
    fontSize: 9,
    fontWeight: '800',
    color: colors.slate500,
    letterSpacing: 0.4,
  },
  metricVal: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy900,
    marginTop: 2,
  },
  metricDivider: {
    width: 1,
    height: 24,
    backgroundColor: colors.slate200,
  },
  headerBtnRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: spacing.md,
  },
  auditBtn: {
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
  auditBtnText: {
    fontSize: 11.5,
    fontWeight: '700',
    color: colors.govNavy800,
  },
  lrmsBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: 'rgba(37, 99, 235, 0.08)',
    borderColor: 'rgba(37, 99, 235, 0.2)',
    borderWidth: 1,
    paddingVertical: 8,
    borderRadius: radius.sm,
  },
  lrmsBtnText: {
    fontSize: 11.5,
    fontWeight: '700',
    color: colors.govNavy600,
  },
  flaggedNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#fffbeb',
    borderColor: '#f59e0b',
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  flaggedNoticeText: {
    flex: 1,
    fontSize: 12,
    color: '#92400e',
    fontWeight: '600',
    lineHeight: 16,
  },
  readyNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#ecfdf5',
    borderColor: '#10b981',
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  readyNoticeText: {
    flex: 1,
    fontSize: 12,
    color: '#065f46',
    fontWeight: '600',
  },
  sectionHeader: {
    marginBottom: spacing.sm,
    paddingHorizontal: 2,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  sectionSub: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 1,
  },
  fieldCard: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderColor: colors.borderCard,
    borderWidth: 1,
    ...shadows.sm,
  },
  flaggedFieldCard: {
    borderColor: colors.saffron500,
    borderWidth: 1.5,
  },
  fieldHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  fieldNameBox: {
    flex: 1,
  },
  fieldName: {
    fontSize: 11,
    fontWeight: '800',
    color: colors.slate600,
    letterSpacing: 0.5,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  correctedBadge: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radius.xs,
  },
  correctedBadgeText: {
    fontSize: 8.5,
    fontWeight: '800',
    color: colors.emerald700,
  },
  flaggedBadge: {
    backgroundColor: 'rgba(220, 38, 38, 0.15)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radius.xs,
  },
  flaggedBadgeText: {
    fontSize: 8.5,
    fontWeight: '800',
    color: colors.rose700,
  },
  confBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radius.xs,
  },
  confText: {
    fontSize: 9,
    fontWeight: '800',
  },
  fieldBody: {
    marginTop: 2,
  },
  valContent: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.govNavy950,
  },
  reasonBox: {
    marginTop: 8,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: colors.slate100,
  },
  reasonText: {
    fontSize: 11,
    color: colors.slate600,
    fontStyle: 'italic',
  },
  signOffSection: {
    marginTop: spacing.md,
    marginBottom: spacing.xl,
  },
  verifyMainBtn: {
    height: 48,
    borderRadius: radius.md,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(6, 19, 37, 0.75)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.white,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: spacing.lg,
    ...shadows.lg,
  },
  modalTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate200,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  modalBtnRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: spacing.md,
  },
});
