import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  ScrollView,
  Image,
  Dimensions,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../i18n/i18n';
import { colors, radius, typography, spacing, shadows } from '../../theme/theme';

const { width } = Dimensions.get('window');
const DRAWER_WIDTH = Math.min(width * 0.82, 340);

export default function SovereignDrawer({ visible, onClose, navigation, currentRoute }) {
  const { user, logout } = useAuth();
  const { t, currentLangObj } = useI18n();

  const navItems = [
    { name: 'Registry', label: 'Operations & Registry', icon: 'file-tray-full-outline', desc: 'Land deeds & analytics' },
    { name: 'Capture', label: 'Digitize & Scan', icon: 'camera-outline', desc: 'Camera capture & OCR' },
    { name: 'Queue', label: 'Offline Sync Queue', icon: 'cloud-upload-outline', desc: 'Local cache & batch sync' },
    { name: 'Audit', label: 'Audit & Compliance', icon: 'shield-checkmark-outline', desc: 'SHA-256 legal ledger' },
    { name: 'Profile', label: 'Officer Settings', icon: 'person-circle-outline', desc: 'Jurisdiction & server node' },
  ];

  const handleNavigate = (screenName) => {
    onClose();
    if (navigation) {
      navigation.navigate(screenName);
    }
  };

  const handleLogout = async () => {
    onClose();
    await logout();
  };

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent={true}
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <TouchableOpacity
          style={styles.backdrop}
          activeOpacity={1}
          onPress={onClose}
        />

        <View style={styles.drawerContent}>
          {/* Sovereign Top Header */}
          <View style={styles.drawerHeader}>
            <View style={styles.govBanner}>
              <Text style={styles.govBannerText}>🇮🇳 GOVT OF INDIA • DILRMP</Text>
              <View style={styles.statusDot}>
                <View style={styles.dotPulse} />
                <Text style={styles.statusText}>Node Active</Text>
              </View>
            </View>

            <View style={styles.brandRow}>
              <Image
                source={require('../../../assets/images/bhoomiscan_logo.png')}
                style={styles.logo}
                resizeMode="contain"
              />
              <View style={styles.brandMeta}>
                <Text style={styles.brandTitle}>BhoomiScan AI</Text>
                <Text style={styles.brandSubtitle}>National Land Records</Text>
              </View>
              <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
                <Ionicons name="close" size={22} color={colors.slate300} />
              </TouchableOpacity>
            </View>

            {/* Officer Profile Card */}
            <View style={styles.officerCard}>
              <View style={styles.officerAvatar}>
                <Text style={styles.avatarInitial}>
                  {(user?.username || 'C')[0].toUpperCase()}
                </Text>
              </View>
              <View style={styles.officerDetails}>
                <Text style={styles.officerName}>{user?.full_name || user?.username || 'Carol'}</Text>
                <View style={styles.roleBadge}>
                  <Text style={styles.roleBadgeText}>
                    {(user?.role || 'FIELD_OFFICER').toUpperCase()}
                  </Text>
                </View>
              </View>
            </View>
          </View>

          {/* Navigation Links */}
          <ScrollView style={styles.navScroll} showsVerticalScrollIndicator={false}>
            <Text style={styles.navSectionTitle}>MAIN MODULES</Text>
            {navItems.map((item) => {
              const isActive = currentRoute === item.name;
              return (
                <TouchableOpacity
                  key={item.name}
                  style={[styles.navItem, isActive && styles.navItemActive]}
                  onPress={() => handleNavigate(item.name)}
                  activeOpacity={0.7}
                >
                  <View style={[styles.navIconBox, isActive && styles.navIconBoxActive]}>
                    <Ionicons
                      name={item.icon}
                      size={20}
                      color={isActive ? colors.saffron500 : colors.slate300}
                    />
                  </View>
                  <View style={styles.navTextContainer}>
                    <Text style={[styles.navLabel, isActive && styles.navLabelActive]}>
                      {item.label}
                    </Text>
                    <Text style={styles.navDesc}>{item.desc}</Text>
                  </View>
                  {isActive ? (
                    <View style={styles.activePill} />
                  ) : (
                    <Ionicons name="chevron-forward" size={16} color={colors.slate600} />
                  )}
                </TouchableOpacity>
              );
            })}

            {/* System Information & Compliance */}
            <View style={styles.complianceCard}>
              <Text style={styles.complianceTitle}>SOVEREIGN STANDARDS</Text>
              <View style={styles.complianceRow}>
                <Ionicons name="checkmark-circle" size={15} color={colors.emerald500} />
                <Text style={styles.complianceText}>ULPIN / Bhu-Aadhaar 14-Digit Sync</Text>
              </View>
              <View style={styles.complianceRow}>
                <Ionicons name="checkmark-circle" size={15} color={colors.emerald500} />
                <Text style={styles.complianceText}>SHA-256 Chain of Custody Audit</Text>
              </View>
              <View style={styles.complianceRow}>
                <Ionicons name="checkmark-circle" size={15} color={colors.emerald500} />
                <Text style={styles.complianceText}>22 Indic Schedule VIII Languages</Text>
              </View>
            </View>
          </ScrollView>

          {/* Drawer Footer */}
          <View style={styles.drawerFooter}>
            <TouchableOpacity
              style={styles.logoutBtn}
              onPress={handleLogout}
              activeOpacity={0.7}
            >
              <Ionicons name="log-out-outline" size={18} color={colors.rose300} />
              <Text style={styles.logoutText}>Sign Out Field Officer</Text>
            </TouchableOpacity>
            <Text style={styles.versionText}>v1.0.0 • GIGW & DILRMP 2.0 Compliant</Text>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    flexDirection: 'row',
  },
  backdrop: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(6, 19, 37, 0.75)',
  },
  drawerContent: {
    width: DRAWER_WIDTH,
    backgroundColor: colors.govNavy950,
    height: '100%',
    borderRightWidth: 1,
    borderRightColor: 'rgba(255, 255, 255, 0.1)',
    ...shadows.lg,
  },
  drawerHeader: {
    paddingTop: Platform.OS === 'ios' ? 48 : 36,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    backgroundColor: colors.govNavy900,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.08)',
  },
  govBanner: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.06)',
  },
  govBannerText: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.saffron400,
    letterSpacing: 0.8,
  },
  statusDot: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  dotPulse: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.emerald500,
  },
  statusText: {
    fontSize: 9,
    color: colors.emerald500,
    fontWeight: '600',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  logo: {
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 1.5,
    borderColor: colors.saffron500,
    marginRight: 10,
  },
  brandMeta: {
    flex: 1,
  },
  brandTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.white,
    letterSpacing: 0.3,
  },
  brandSubtitle: {
    fontSize: 11,
    color: colors.slate400,
  },
  closeBtn: {
    padding: 4,
  },
  officerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.govNavy850,
    borderRadius: radius.md,
    padding: 10,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  officerAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.govNavy700,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: colors.saffron500,
    marginRight: 10,
  },
  avatarInitial: {
    color: colors.saffron400,
    fontSize: 16,
    fontWeight: '800',
  },
  officerDetails: {
    flex: 1,
  },
  officerName: {
    color: colors.white,
    fontSize: 13,
    fontWeight: '700',
  },
  roleBadge: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radius.xs,
    marginTop: 2,
  },
  roleBadgeText: {
    color: colors.saffron400,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  navScroll: {
    flex: 1,
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.md,
  },
  navSectionTitle: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.slate500,
    letterSpacing: 0.8,
    marginBottom: spacing.xs,
    marginLeft: spacing.xs,
  },
  navItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radius.md,
    marginBottom: 4,
  },
  navItemActive: {
    backgroundColor: colors.govNavy900,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  navIconBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  navIconBoxActive: {
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
  },
  navTextContainer: {
    flex: 1,
  },
  navLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.slate200,
  },
  navLabelActive: {
    color: colors.white,
    fontWeight: '700',
  },
  navDesc: {
    fontSize: 10,
    color: colors.slate500,
    marginTop: 1,
  },
  activePill: {
    width: 4,
    height: 18,
    borderRadius: 2,
    backgroundColor: colors.saffron500,
  },
  complianceCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
  },
  complianceTitle: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.saffron400,
    letterSpacing: 0.6,
    marginBottom: 8,
  },
  complianceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  complianceText: {
    fontSize: 11,
    color: colors.slate300,
    flex: 1,
  },
  drawerFooter: {
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.08)',
    backgroundColor: colors.govNavy900,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: 'rgba(220, 38, 38, 0.12)',
    paddingVertical: 10,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: 'rgba(220, 38, 38, 0.25)',
  },
  logoutText: {
    color: colors.rose300,
    fontSize: 12,
    fontWeight: '700',
  },
  versionText: {
    color: colors.slate500,
    fontSize: 9,
    textAlign: 'center',
    marginTop: 8,
  },
});
