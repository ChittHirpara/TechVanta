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
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../i18n/i18n';
import { clearCompletedQueueItems, getQueueItems } from '../utils/queueDatabase';
import { getApiBaseUrl, setCustomApiBaseUrl } from '../api/client';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Input from '../components/common/Input';
import { colors, radius, typography, spacing, shadows } from '../theme/theme';

export default function ProfileScreen({ navigation }) {
  const { user, logout } = useAuth();
  const { language, setLanguage, currentLangObj, languages, t } = useI18n();
  const [langModalVisible, setLangModalVisible] = useState(false);
  const [queueStats, setQueueStats] = useState({ total: 0, uploaded: 0, pending: 0 });
  const [serverUrl, setServerUrl] = useState(getApiBaseUrl());
  const [serverModalVisible, setServerModalVisible] = useState(false);

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

  const handleSaveServerUrl = async (url) => {
    await setCustomApiBaseUrl(url);
    setServerUrl(getApiBaseUrl());
    setServerModalVisible(false);
    Alert.alert('Endpoint Updated', `Active API target: ${getApiBaseUrl()}`);
  };

  const handleClearCache = async () => {
    Alert.alert(
      'Clear Synced Cache',
      'This will remove local image copies of already synced records to free device storage. Queued items will remain safe.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear Cache',
          onPress: async () => {
            await clearCompletedQueueItems();
            await loadStats();
            Alert.alert('Storage Cleaned', 'Completed captures cleared from local storage.');
          },
        },
      ]
    );
  };

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out from BhoomiScan AI?', [
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
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
      {/* Officer ID Card */}
      <Card style={styles.profileCard}>
        <View style={styles.avatarRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {(user?.username || 'C')[0].toUpperCase()}
            </Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.userName}>{user?.full_name || user?.username || 'Carol'}</Text>
            <View style={styles.roleBadge}>
              <Text style={styles.roleBadgeText}>
                {(user?.role || 'FIELD_OFFICER').toUpperCase()}
              </Text>
            </View>
            <Text style={styles.jurisdictionText}>
              Jaipur Revenue Division • DoLR Govt. of India
            </Text>
          </View>
        </View>
      </Card>

      {/* Sovereign System Settings */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>SYSTEM & LANGUAGE SETTINGS</Text>
      </View>

      <Card style={styles.settingsCard}>
        {/* Language Selection */}
        <TouchableOpacity
          style={styles.settingRow}
          onPress={() => setLangModalVisible(true)}
          activeOpacity={0.7}
        >
          <View style={styles.settingLeft}>
            <View style={styles.settingIconBox}>
              <Ionicons name="globe-outline" size={18} color={colors.saffron500} />
            </View>
            <View>
              <Text style={styles.settingLabel}>Regional Language</Text>
              <Text style={styles.settingValue}>
                {currentLangObj?.name} ({currentLangObj?.nativeName})
              </Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.slate400} />
        </TouchableOpacity>

        <View style={styles.settingDivider} />

        {/* Server Endpoint URL */}
        <TouchableOpacity
          style={styles.settingRow}
          onPress={() => setServerModalVisible(true)}
          activeOpacity={0.7}
        >
          <View style={styles.settingLeft}>
            <View style={styles.settingIconBox}>
              <Ionicons name="server-outline" size={18} color={colors.govNavy600} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.settingLabel}>Backend API Gateway</Text>
              <Text style={styles.settingValue} numberOfLines={1}>{serverUrl}</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.slate400} />
        </TouchableOpacity>

        <View style={styles.settingDivider} />

        {/* Offline Sync Cache */}
        <TouchableOpacity
          style={styles.settingRow}
          onPress={handleClearCache}
          activeOpacity={0.7}
        >
          <View style={styles.settingLeft}>
            <View style={styles.settingIconBox}>
              <Ionicons name="trash-bin-outline" size={18} color={colors.slate600} />
            </View>
            <View>
              <Text style={styles.settingLabel}>Local Storage Cache</Text>
              <Text style={styles.settingValue}>
                {queueStats.uploaded} Synced • {queueStats.pending} Pending
              </Text>
            </View>
          </View>
          <Text style={styles.clearBtnText}>Clean</Text>
        </TouchableOpacity>
      </Card>

      {/* Compliance Information */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>SOVEREIGN GOVERNANCE SPECIFICATIONS</Text>
      </View>

      <Card style={styles.complianceCard}>
        <View style={styles.complianceItem}>
          <Ionicons name="shield-checkmark" size={16} color={colors.emerald600} />
          <View style={styles.complianceTextWrapper}>
            <Text style={styles.complianceHeader}>DILRMP Technical Core</Text>
            <Text style={styles.complianceDetail}>Mandatory 6 legal attribute extraction matrix</Text>
          </View>
        </View>

        <View style={styles.complianceItem}>
          <Ionicons name="barcode-outline" size={16} color={colors.saffron600} />
          <View style={styles.complianceTextWrapper}>
            <Text style={styles.complianceHeader}>Bhu-Aadhaar (ULPIN)</Text>
            <Text style={styles.complianceDetail}>14-digit geo-referenced cadastral identifier</Text>
          </View>
        </View>

        <View style={styles.complianceItem}>
          <Ionicons name="lock-closed" size={16} color={colors.govNavy600} />
          <View style={styles.complianceTextWrapper}>
            <Text style={styles.complianceHeader}>SHA-256 Ledger Security</Text>
            <Text style={styles.complianceDetail}>Cryptographic state signatures for civil litigation defense</Text>
          </View>
        </View>
      </Card>

      {/* Sign Out Button */}
      <Button
        title="Sign Out Field Officer"
        onPress={handleLogout}
        variant="danger"
        style={styles.logoutBtn}
      />

      {/* Language Modal */}
      <Modal
        visible={langModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setLangModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalTop}>
              <Text style={styles.modalTitle}>Select Language / भाषा चुनें</Text>
              <TouchableOpacity onPress={() => setLangModalVisible(false)}>
                <Ionicons name="close" size={20} color={colors.slate600} />
              </TouchableOpacity>
            </View>
            <FlatList
              data={languages}
              keyExtractor={(item) => item.code}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.langItem, language === item.code && styles.langItemActive]}
                  onPress={() => {
                    setLanguage(item.code);
                    setLangModalVisible(false);
                  }}
                >
                  <View>
                    <Text style={[styles.langName, language === item.code && styles.langNameActive]}>
                      {item.name}
                    </Text>
                    <Text style={styles.langNative}>{item.nativeName}</Text>
                  </View>
                  {language === item.code && (
                    <Ionicons name="checkmark-circle" size={20} color={colors.emerald600} />
                  )}
                </TouchableOpacity>
              )}
            />
          </View>
        </View>
      </Modal>

      {/* Server URL Modal */}
      <Modal
        visible={serverModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setServerModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalTop}>
              <Text style={styles.modalTitle}>Configure API Gateway</Text>
              <TouchableOpacity onPress={() => setServerModalVisible(false)}>
                <Ionicons name="close" size={20} color={colors.slate600} />
              </TouchableOpacity>
            </View>

            <Input
              label="Backend Endpoint URL"
              value={serverUrl}
              onChangeText={setServerUrl}
              placeholder="http://10.143.194.49:8000/api/v1"
              autoCapitalize="none"
            />

            <View style={styles.presetRow}>
              <TouchableOpacity
                style={styles.presetChip}
                onPress={() => handleSaveServerUrl('http://10.143.194.49:8000/api/v1')}
              >
                <Text style={styles.presetChipText}>📡 Wi-Fi (10.143.194.49)</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.presetChip}
                onPress={() => handleSaveServerUrl('http://localhost:8000/api/v1')}
              >
                <Text style={styles.presetChipText}>💻 Localhost:8000</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.presetChip}
                onPress={() => handleSaveServerUrl('http://10.0.2.2:8000/api/v1')}
              >
                <Text style={styles.presetChipText}>📱 Emulator (10.0.2.2)</Text>
              </TouchableOpacity>
            </View>

            <Button
              title="Apply Server Endpoint"
              onPress={() => handleSaveServerUrl(serverUrl)}
              variant="saffron"
              style={{ marginTop: spacing.md }}
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
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    marginBottom: spacing.md,
    ...shadows.sm,
  },
  avatarRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.govNavy900,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.saffron500,
    marginRight: 12,
  },
  avatarText: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.saffron400,
  },
  profileInfo: {
    flex: 1,
  },
  userName: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  roleBadge: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.xs,
    marginVertical: 3,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  roleBadgeText: {
    fontSize: 9.5,
    fontWeight: '800',
    color: colors.saffron700,
    letterSpacing: 0.4,
  },
  jurisdictionText: {
    fontSize: 10.5,
    color: colors.slate500,
  },
  sectionHeader: {
    marginTop: spacing.sm,
    marginBottom: 6,
    paddingHorizontal: 2,
  },
  sectionTitle: {
    fontSize: 10.5,
    fontWeight: '800',
    color: colors.slate500,
    letterSpacing: 0.6,
  },
  settingsCard: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.sm,
    borderColor: colors.borderCard,
    borderWidth: 1,
    marginBottom: spacing.md,
    ...shadows.sm,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 8,
  },
  settingLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 10,
  },
  settingIconBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: colors.govNavy50,
    alignItems: 'center',
    justifyContent: 'center',
  },
  settingLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.govNavy950,
  },
  settingValue: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 1,
  },
  settingDivider: {
    height: 1,
    backgroundColor: colors.slate100,
    marginHorizontal: 8,
  },
  clearBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.rose600,
  },
  complianceCard: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    marginBottom: spacing.lg,
    ...shadows.sm,
    gap: 12,
  },
  complianceItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  complianceTextWrapper: {
    flex: 1,
  },
  complianceHeader: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.govNavy900,
  },
  complianceDetail: {
    fontSize: 10.5,
    color: colors.slate500,
    marginTop: 1,
  },
  logoutBtn: {
    marginBottom: spacing.xl,
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
    maxHeight: '75%',
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
  langItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: radius.md,
    marginBottom: 4,
    backgroundColor: colors.slate50,
  },
  langItemActive: {
    backgroundColor: colors.emerald50,
    borderWidth: 1,
    borderColor: colors.emerald500,
  },
  langName: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.slate800,
  },
  langNameActive: {
    color: colors.emerald800,
    fontWeight: '700',
  },
  langNative: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 1,
  },
  presetRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: spacing.xs,
  },
  presetChip: {
    backgroundColor: colors.govNavy50,
    borderColor: colors.govNavy100,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.sm,
  },
  presetChipText: {
    fontSize: 11,
    color: colors.govNavy800,
    fontWeight: '600',
  },
});
