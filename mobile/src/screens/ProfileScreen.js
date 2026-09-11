import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Modal,
  FlatList,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../i18n/i18n';
import { clearCompletedQueueItems, getQueueItems } from '../utils/queueDatabase';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing } from '../theme/theme';

export default function ProfileScreen({ navigation }) {
  const { user, logout } = useAuth();
  const { language, setLanguage, currentLangObj, languages, t } = useI18n();
  const [langModalVisible, setLangModalVisible] = useState(false);
  const [queueStats, setQueueStats] = useState({ total: 0, uploaded: 0, pending: 0 });

  const loadStats = async () => {
    try {
      const items = await getQueueItems();
      const uploaded = items.filter((i) => i.status === 'uploaded').length;
      const pending = items.filter((i) => i.status === 'queued' || i.status === 'failed').length;
      setQueueStats({ total: items.length, uploaded, pending });
    } catch (e) {}
  };

  useEffect(() => {
    loadStats();
  }, []);

  const handleClearCache = async () => {
    Alert.alert(
      'Clear Cache',
      'This will remove local image copies of already synced records to free device space. Queued items will NOT be deleted.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear Cache',
          onPress: async () => {
            await clearCompletedQueueItems();
            await loadStats();
            Alert.alert('Cache Cleared', 'Completed captures cleared from local storage.');
          },
        },
      ]
    );
  };

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: async () => {
          await logout();
        },
      },
    ]);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* Officer ID Card */}
      <Card style={styles.profileCard}>
        <View style={styles.avatarRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>👮</Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.userName}>{user?.username || 'Field Officer'}</Text>
            <View style={styles.roleBadge}>
              <Text style={styles.roleBadgeText}>GOVERNMENT FIELD OFFICER</Text>
            </View>
            <Text style={styles.jurisdictionText}>
              National Land Records Modernization Program (DILRMP), Govt. of India
            </Text>
          </View>
        </View>
      </Card>

      {/* Language Selection */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Regional Language</Text>
      </View>
      <Card style={styles.card}>
        <TouchableOpacity
          style={styles.settingRow}
          onPress={() => setLangModalVisible(true)}
        >
          <View>
            <Text style={styles.settingLabel}>{t('profile_language')}</Text>
            <Text style={styles.settingValue}>
              {currentLangObj.name} ({currentLangObj.nativeName})
            </Text>
          </View>
          <Text style={styles.chevron}>🌐 Change</Text>
        </TouchableOpacity>
      </Card>

      {/* Offline Storage & Queue Stats */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Local Storage & Queue</Text>
      </View>
      <Card style={styles.card}>
        <View style={styles.statRow}>
          <View style={styles.statBox}>
            <Text style={styles.statNumber}>{queueStats.pending}</Text>
            <Text style={styles.statLabel}>Pending Sync</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statNumber}>{queueStats.uploaded}</Text>
            <Text style={styles.statLabel}>Synced</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statNumber}>{queueStats.total}</Text>
            <Text style={styles.statLabel}>Total Local</Text>
          </View>
        </View>

        <TouchableOpacity style={styles.clearBtn} onPress={handleClearCache}>
          <Text style={styles.clearBtnText}>🧹 {t('profile_clear_cache')}</Text>
        </TouchableOpacity>
      </Card>

      {/* App & System Specs */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Application Information</Text>
      </View>
      <Card style={styles.card}>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>System Theme</Text>
          <Text style={styles.infoVal}>GIGW Land Registry Sovereign</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>App Version</Text>
          <Text style={styles.infoVal}>v2.4.0 (SIH26018 Production)</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Sync Architecture</Text>
          <Text style={styles.infoVal}>Offline-First SQLite + NetInfo</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Languages Supported</Text>
          <Text style={styles.infoVal}>22 Schedule VIII Indian Languages</Text>
        </View>
      </Card>

      {/* Sign Out */}
      <Button
        title={t('logout')}
        variant="danger"
        onPress={handleLogout}
        style={{ marginTop: spacing.lg }}
      />

      {/* Language Selector Modal */}
      <Modal
        visible={langModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setLangModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Regional Language</Text>
              <TouchableOpacity onPress={() => setLangModalVisible(false)}>
                <Text style={styles.closeText}>✕</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.modalSub}>
              Choose from 22 official Schedule VIII Indian languages
            </Text>

            <FlatList
              data={languages}
              keyExtractor={(item) => item.code}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.langItem,
                    language === item.code && styles.langItemActive,
                  ]}
                  onPress={() => {
                    setLanguage(item.code);
                    setLangModalVisible(false);
                  }}
                >
                  <View>
                    <Text
                      style={[
                        styles.langName,
                        language === item.code && styles.langNameActive,
                      ]}
                    >
                      {item.name}
                    </Text>
                    <Text style={styles.langNative}>{item.nativeName}</Text>
                  </View>
                  {language === item.code ? (
                    <Text style={styles.checkIcon}>✓</Text>
                  ) : null}
                </TouchableOpacity>
              )}
            />
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
  profileCard: {
    backgroundColor: colors.govNavy900,
    marginBottom: spacing.md,
  },
  avatarRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.govNavy800,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  avatarText: {
    fontSize: 28,
  },
  profileInfo: {
    flex: 1,
  },
  userName: {
    fontSize: typography.sizes.lg,
    fontWeight: '700',
    color: colors.white,
  },
  roleBadge: {
    backgroundColor: colors.saffron600,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.full,
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  roleBadgeText: {
    color: colors.white,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  jurisdictionText: {
    fontSize: typography.sizes.xs,
    color: colors.slate300,
    marginTop: 4,
  },
  sectionHeader: {
    marginTop: spacing.md,
    marginBottom: spacing.xs,
  },
  sectionTitle: {
    fontSize: typography.sizes.sm,
    fontWeight: '700',
    color: colors.slate700,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  card: {
    marginBottom: spacing.xs,
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.xs,
  },
  settingLabel: {
    fontSize: typography.sizes.md,
    fontWeight: '600',
    color: colors.slate800,
  },
  settingValue: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  chevron: {
    fontSize: typography.sizes.sm,
    color: colors.govNavy600,
    fontWeight: '600',
  },
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate100,
  },
  statBox: {
    alignItems: 'center',
  },
  statNumber: {
    fontSize: typography.sizes.xl,
    fontWeight: '800',
    color: colors.govNavy900,
  },
  statLabel: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  clearBtn: {
    marginTop: spacing.sm,
    padding: spacing.xs,
    alignItems: 'center',
  },
  clearBtnText: {
    fontSize: typography.sizes.xs,
    color: colors.rose700,
    fontWeight: '600',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate100,
  },
  infoLabel: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
  },
  infoVal: {
    fontSize: typography.sizes.xs,
    fontWeight: '600',
    color: colors.slate900,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.white,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    maxHeight: '80%',
    padding: spacing.md,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: typography.sizes.lg,
    fontWeight: '700',
    color: colors.slate900,
  },
  modalSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginBottom: spacing.md,
    marginTop: 2,
  },
  closeText: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.slate500,
  },
  langItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate100,
  },
  langItemActive: {
    backgroundColor: colors.govNavy50,
  },
  langName: {
    fontSize: typography.sizes.md,
    fontWeight: '600',
    color: colors.slate800,
  },
  langNameActive: {
    color: colors.govNavy700,
    fontWeight: '700',
  },
  langNative: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  checkIcon: {
    fontSize: typography.sizes.md,
    fontWeight: '700',
    color: colors.govNavy600,
  },
});
