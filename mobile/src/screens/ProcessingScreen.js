import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { createDocumentEventSource, documentsApi } from '../api/client';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Badge from '../components/common/Badge';
import { colors, radius, typography, spacing } from '../theme/theme';

const PIPELINE_STAGES = [
  { id: 'ocr', label: 'OCR Text Recognition', icon: '🔍', startStep: 'ocr_started', completeStep: 'ocr_complete' },
  { id: 'extraction', label: 'AI LLM Field Extraction', icon: '🤖', startStep: 'extraction_started', completeStep: 'extraction_complete' },
  { id: 'validation', label: 'Rules & Duplicate Validation', icon: '🛡️', startStep: 'validation', completeStep: 'validation' },
  { id: 'persistence', label: 'DB Record Persistence', icon: '💾', startStep: 'persist_fields', completeStep: 'persist_fields' },
];

export default function ProcessingScreen({ route, navigation }) {
  const { documentId } = route.params || {};

  const [currentStep, setCurrentStep] = useState('ocr_started');
  const [percent, setPercent] = useState(15);
  const [message, setMessage] = useState('Initializing extraction pipeline...');
  const [status, setStatus] = useState('processing');
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState(null);
  const [eventsList, setEventsList] = useState([]);

  const eventSourceRef = useRef(null);

  useEffect(() => {
    if (!documentId) {
      setError('No Document ID provided for processing.');
      return;
    }

    let isMounted = true;

    async function connectSSE() {
      try {
        const es = await createDocumentEventSource(
          documentId,
          (data) => {
            if (!isMounted) return;

            if (data) {
              setEventsList((prev) => [...prev, data]);

              if (data.step) setCurrentStep(data.step);
              if (data.percent != null) setPercent(data.percent);
              if (data.message) setMessage(data.message);
              if (data.status) setStatus(data.status);

              if (data.event === 'complete' || data.step === 'complete') {
                setPercent(100);
                setCompleted(true);
                // Auto-navigate to Review Screen after 1.5s
                setTimeout(() => {
                  if (isMounted) {
                    navigation.replace('Review', { documentId });
                  }
                }, 1500);
              }

              if (data.event === 'error') {
                setError(data.message || 'Pipeline processing error encountered.');
              }
            }
          },
          (err) => {
            if (!isMounted) return;
            console.warn('SSE connection error, fallback polling enabled:', err);
          }
        );

        eventSourceRef.current = es;
      } catch (err) {
        if (isMounted) {
          console.warn('Failed to open EventSource stream:', err);
        }
      }
    }

    connectSSE();

    // Fallback status checker poll in case SSE stream closes early
    const interval = setInterval(async () => {
      if (completed || error) return;
      try {
        const doc = await documentsApi.get(documentId);
        if (doc && (doc.status === 'needs_review' || doc.status === 'verified')) {
          setPercent(100);
          setStatus(doc.status);
          setCompleted(true);
          setTimeout(() => {
            if (isMounted) {
              navigation.replace('Review', { documentId });
            }
          }, 1000);
        }
      } catch (e) {
        // ignore polling errors
      }
    }, 4000);

    return () => {
      isMounted = false;
      clearInterval(interval);
      if (eventSourceRef.current) {
        try {
          eventSourceRef.current.close();
        } catch (e) {}
      }
    };
  }, [documentId, navigation, completed, error]);

  const getStageStatus = (stage) => {
    const stepOrder = [
      'ocr_started',
      'ocr_complete',
      'extraction_started',
      'extraction_complete',
      'validation',
      'persist_fields',
      'complete',
    ];

    const currentIdx = stepOrder.indexOf(currentStep);
    const startIdx = stepOrder.indexOf(stage.startStep);
    const completeIdx = stepOrder.indexOf(stage.completeStep);

    if (completed || currentIdx > completeIdx) {
      return 'completed';
    } else if (currentIdx >= startIdx) {
      return 'active';
    } else {
      return 'pending';
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Live Pipeline Execution</Text>
        <Text style={styles.headerSub}>
          Document ID #{documentId} • Real-time SSE Stream
        </Text>
      </View>

      {error ? (
        <Card style={styles.errorCard}>
          <Text style={styles.errorTitle}>⚠️ Processing Error</Text>
          <Text style={styles.errorText}>{error}</Text>
          <Button
            title="Proceed to Manual Review"
            onPress={() => navigation.replace('Review', { documentId })}
            variant="saffron"
            style={{ marginTop: spacing.md }}
          />
        </Card>
      ) : null}

      {/* Main Progress Indicator */}
      <Card style={styles.progressCard}>
        <View style={styles.statusRow}>
          <Text style={styles.percentText}>{percent}%</Text>
          <Badge status={completed ? status : 'processing'} />
        </View>

        <View style={styles.track}>
          <View style={[styles.bar, { width: `${percent}%` }]} />
        </View>

        <Text style={styles.messageText}>
          {!completed ? '⏳ ' : '✅ '}
          {message}
        </Text>

        {completed ? (
          <View style={styles.completeNotice}>
            <Text style={styles.completeTitle}>
              🎉 Pipeline Ingestion Complete!
            </Text>
            <Text style={styles.completeSub}>
              Redirecting to verification & field review...
            </Text>
          </View>
        ) : null}
      </Card>

      {/* Stage Breakdown List */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Pipeline Stage Tracker</Text>
      </View>

      {PIPELINE_STAGES.map((stage) => {
        const stageState = getStageStatus(stage);
        return (
          <Card key={stage.id} style={styles.stageCard}>
            <View style={styles.stageRow}>
              <Text style={styles.stageIcon}>{stage.icon}</Text>
              <View style={styles.stageContent}>
                <Text style={styles.stageTitle}>{stage.label}</Text>
                <Text style={styles.stageSub}>
                  {stageState === 'completed'
                    ? 'Completed successfully'
                    : stageState === 'active'
                    ? 'In progress...'
                    : 'Queued'}
                </Text>
              </View>
              {stageState === 'completed' ? (
                <Text style={styles.checkIcon}>✅</Text>
              ) : stageState === 'active' ? (
                <ActivityIndicator size="small" color={colors.saffron600} />
              ) : (
                <View style={styles.pendingDot} />
              )}
            </View>
          </Card>
        );
      })}

      {/* Live Event Log Stream */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>SSE Real-Time Event Log</Text>
      </View>

      <Card style={styles.logCard}>
        <ScrollView style={styles.logScroll} nestedScrollEnabled>
          {eventsList.length > 0 ? (
            eventsList.map((ev, i) => (
              <Text key={i} style={styles.logLine}>
                <Text style={styles.logTime}>[{new Date().toLocaleTimeString()}] </Text>
                <Text style={styles.logEvent}>[{ev.event || ev.step}] </Text>
                {ev.message}
              </Text>
            ))
          ) : (
            <Text style={styles.emptyLog}>Listening for server events via EventSource...</Text>
          )}
        </ScrollView>
      </Card>

      <Button
        title="View Document Details"
        onPress={() => navigation.replace('Review', { documentId })}
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
  header: {
    marginBottom: spacing.md,
  },
  headerTitle: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  headerSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    marginTop: 2,
  },
  errorCard: {
    backgroundColor: colors.rose50,
    borderColor: colors.rose600,
  },
  errorTitle: {
    color: colors.rose800,
    fontWeight: typography.weights.bold,
    fontSize: typography.sizes.md,
  },
  errorText: {
    color: colors.rose700,
    fontSize: typography.sizes.xs,
    marginTop: 4,
  },
  progressCard: {
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  percentText: {
    fontSize: typography.sizes.xxl,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  track: {
    height: 10,
    backgroundColor: colors.slate200,
    borderRadius: radius.full,
    overflow: 'hidden',
    marginBottom: spacing.sm,
  },
  bar: {
    height: '100%',
    backgroundColor: colors.saffron600,
    borderRadius: radius.full,
  },
  messageText: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.medium,
    color: colors.slate700,
  },
  completeNotice: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.slate200,
    alignItems: 'center',
  },
  completeTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    color: colors.emerald700,
  },
  completeSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    marginTop: 2,
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
  stageCard: {
    marginBottom: spacing.xs,
    paddingVertical: spacing.md,
  },
  stageRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  stageIcon: {
    fontSize: 22,
    marginRight: spacing.md,
  },
  stageContent: {
    flex: 1,
  },
  stageTitle: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  stageSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  checkIcon: {
    fontSize: 18,
  },
  pendingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.slate300,
  },
  logCard: {
    backgroundColor: colors.slate950,
    borderColor: colors.slate800,
  },
  logScroll: {
    maxHeight: 140,
  },
  logLine: {
    fontFamily: typography.fontFamily.mono,
    fontSize: 11,
    color: colors.slate300,
    marginBottom: 4,
  },
  logTime: {
    color: colors.slate500,
  },
  logEvent: {
    color: colors.saffron500,
    fontWeight: typography.weights.bold,
  },
  emptyLog: {
    fontFamily: typography.fontFamily.mono,
    fontSize: 11,
    color: colors.slate500,
    fontStyle: 'italic',
  },
});
