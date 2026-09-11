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
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing } from '../theme/theme';

export default function ReviewScreen({ route, navigation }) {
  const { documentId } = route.params || {};

  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const fetchDocument = useCallback(async () => {
    if (!documentId) return;
    try {
      setError(null);
      const data = await documentsApi.get(documentId);
      setDocument(data);
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

  if (loading && !refreshing) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.govNavy600} />
        <Text style={styles.loadingText}>Loading Document Record #{documentId}...</Text>
      </View>
    );
  }

  const fields = document?.extracted_fields || [];
  const flaggedCount = fields.filter((f) => f.is_flagged && !f.is_overridden).length;

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
      {/* Header Banner */}
      <Card style={styles.docHeaderCard}>
        <View style={styles.titleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.docTitle}>{document?.title || `Document #${documentId}`}</Text>
            <Text style={styles.docMeta}>
              District: {document?.district || 'N/A'} • Uploaded:{' '}
              {document?.created_at
                ? new Date(document.created_at).toLocaleDateString()
                : 'Recent'}
            </Text>
          </View>
          <Badge status={document?.status} />
        </View>

        <View style={styles.actionRow}>
          <Button
            title="📜 View Audit Trail"
            onPress={() => navigation.navigate('Audit', { documentId })}
            variant="outline"
            style={{ flex: 1 }}
          />
        </View>
      </Card>

      {error ? (
        <Card style={styles.errorCard}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
          <Button title="Retry Loading" onPress={fetchDocument} variant="outline" style={{ marginTop: spacing.sm }} />
        </Card>
      ) : null}

      {/* Verification Notice */}
      {flaggedCount > 0 ? (
        <View style={styles.flaggedNotice}>
          <Text style={styles.flaggedNoticeText}>
            🚩 {flaggedCount} {flaggedCount === 1 ? 'attribute requires' : 'attributes require'} manual review. Field verification & editing must be performed on the Web Dashboard.
          </Text>
        </View>
      ) : (
        <View style={styles.readyNotice}>
          <Text style={styles.readyNoticeText}>
            ✨ All extracted fields verified and confidence score compliant.
          </Text>
        </View>
      )}

      {/* Extracted Fields Section */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Extracted Land Attributes ({fields.length})</Text>
        <Text style={styles.sectionSub}>Read-only view of extracted OCR & LLM data</Text>
      </View>

      {fields.map((field) => {
        const confPct = Math.round((field.confidence_score || 0) * 100);
        const isHighConf = confPct >= 85;
        const isLowConf = confPct < 70;

        return (
          <Card key={field.id || field.field_name} style={[styles.fieldCard, field.is_flagged && styles.flaggedFieldCard]}>
            <View style={styles.fieldHeader}>
              <Text style={styles.fieldName}>
                {field.field_name ? field.field_name.replace(/_/g, ' ').toUpperCase() : 'FIELD'}
              </Text>
              <View style={styles.badgeRow}>
                {field.is_overridden ? (
                  <Badge status="verified" label="CORRECTED" style={{ marginRight: 4 }} />
                ) : null}
                {field.is_flagged ? (
                  <Badge status="flagged" label="FLAGGED" style={{ marginRight: 4 }} />
                ) : null}
                <View
                  style={[
                    styles.confBadge,
                    {
                      backgroundColor: isHighConf
                        ? colors.emerald100
                        : isLowConf
                        ? colors.rose100
                        : colors.saffron100,
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.confText,
                      {
                        color: isHighConf
                          ? colors.emerald800
                          : isLowConf
                          ? colors.rose800
                          : colors.saffron900,
                      },
                    ]}
                  >
                    {confPct}% conf
                  </Text>
                </View>
              </View>
            </View>

            <View style={styles.fieldBody}>
              <View style={styles.valCol}>
                <Text style={styles.valLabel}>Extracted Value:</Text>
                <Text style={styles.valContent}>
                  {field.verified_value || field.extracted_value || 'N/A'}
                </Text>
              </View>
            </View>

            {field.correction_reason ? (
              <Text style={styles.reasonText}>Correction Note: {field.correction_reason}</Text>
            ) : null}
          </Card>
        );
      })}
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
    padding: spacing.xl,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: spacing.md,
    color: colors.slate600,
    fontSize: typography.sizes.sm,
  },
  docHeaderCard: {
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
  },
  docTitle: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  docMeta: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  actionRow: {
    flexDirection: 'row',
    marginTop: spacing.xs,
  },
  errorCard: {
    backgroundColor: colors.rose50,
    borderColor: colors.rose600,
  },
  errorText: {
    color: colors.rose800,
    fontSize: typography.sizes.sm,
  },
  flaggedNotice: {
    backgroundColor: colors.saffron50,
    borderColor: colors.saffron500,
    borderWidth: 1,
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.md,
  },
  flaggedNoticeText: {
    color: colors.saffron900,
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.semibold,
  },
  readyNotice: {
    backgroundColor: colors.emerald50,
    borderColor: colors.emerald500,
    borderWidth: 1,
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.md,
  },
  readyNoticeText: {
    color: colors.emerald800,
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.semibold,
  },
  sectionHeader: {
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
  fieldCard: {
    marginBottom: spacing.xs,
    padding: spacing.md,
  },
  flaggedFieldCard: {
    borderColor: colors.rose600,
    borderWidth: 1.5,
    backgroundColor: '#fffdfd',
  },
  fieldHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  fieldName: {
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.bold,
    color: colors.govNavy800,
    letterSpacing: 0.5,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  confBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  confText: {
    fontSize: 10,
    fontWeight: typography.weights.bold,
  },
  fieldBody: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  valCol: {
    flex: 1,
  },
  valLabel: {
    fontSize: 10,
    color: colors.slate500,
  },
  valContent: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.semibold,
    color: colors.slate900,
    marginTop: 1,
  },
  reasonText: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    fontStyle: 'italic',
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.slate200,
  },
});
