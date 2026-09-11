import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Modal, FlatList, Image } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../i18n/i18n';
import { colors, radius, typography, spacing } from '../../theme/theme';

export default function GovHeader() {
  const navigation = useNavigation();
  const { user, isAuthenticated } = useAuth();
  const { t, language, setLanguage, currentLangObj, languages } = useI18n();
  const [langModalOpen, setLangModalOpen] = useState(false);

  return (
    <View style={styles.header}>
      <View style={styles.topRow}>
        <TouchableOpacity
          style={styles.brandRow}
          onPress={() => isAuthenticated && navigation.navigate('Registry')}
          activeOpacity={0.8}
        >
          <Image
            source={require('../../../assets/images/BhoomiScan_AI_Logo_Icon_Transparent.png')}
            style={styles.logoIcon}
            resizeMode="contain"
          />
          <View style={styles.brandTitleContainer}>
            <Text style={styles.brandTitle}>{t('app_title') || 'BhoomiScan AI'}</Text>
            <Text style={styles.brandSub}>{t('app_subtitle') || 'National Land Record Digitization'}</Text>
          </View>
        </TouchableOpacity>

        <View style={styles.headerActions}>
          <TouchableOpacity
            activeOpacity={0.8}
            onPress={() => setLangModalOpen(true)}
            style={styles.langBtn}
          >
            <Text style={styles.langBtnText}>🌐 {currentLangObj?.nativeName || 'Language'}</Text>
          </TouchableOpacity>

          {isAuthenticated ? (
            <TouchableOpacity
              activeOpacity={0.8}
              onPress={() => navigation.navigate('Profile')}
              style={styles.profileBtn}
            >
              <Text style={styles.profileBtnText}>⚙️</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </View>

      {isAuthenticated && user ? (
        <View style={styles.navBar}>
          <TouchableOpacity
            style={styles.navItem}
            onPress={() => navigation.navigate('Registry')}
          >
            <Text style={styles.navText}>📋 {t('nav_registry') || 'Records'}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.navItem}
            onPress={() => navigation.navigate('Capture')}
          >
            <Text style={styles.navText}>📸 {t('nav_capture') || 'Scan'}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.navItem}
            onPress={() => navigation.navigate('Queue')}
          >
            <Text style={styles.navText}>📦 {t('nav_queue') || 'Queue'}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.navItem}
            onPress={() => navigation.navigate('Profile')}
          >
            <Text style={styles.navText}>👤 {t('profile_title') || 'Profile'}</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {/* Language Selection Modal */}
      <Modal
        visible={langModalOpen}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setLangModalOpen(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Language / भाषा चुनें</Text>
              <TouchableOpacity onPress={() => setLangModalOpen(false)}>
                <Text style={styles.closeText}>✕</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.modalSub}>
              22 Official Schedule VIII Indian Languages
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
                    setLangModalOpen(false);
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
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: colors.govNavy900,
    paddingTop: 45,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  logoIcon: {
    width: 38,
    height: 38,
    marginRight: 10,
  },
  emblemBadge: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.govNavy800,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
    borderWidth: 1,
    borderColor: colors.saffron500,
  },
  emblemIcon: {
    fontSize: 18,
  },
  brandTitleContainer: {
    justifyContent: 'center',
  },
  brandTitle: {
    color: colors.white,
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    letterSpacing: 0.5,
  },
  brandSub: {
    color: colors.slate400,
    fontSize: 10,
  },
  langBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
    borderRadius: radius.sm,
    backgroundColor: colors.govNavy800,
    borderWidth: 1,
    borderColor: colors.saffron500,
  },
  langBtnText: {
    color: colors.saffron300,
    fontSize: 11,
    fontWeight: typography.weights.bold,
  },
  profileBtn: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: radius.sm,
    backgroundColor: colors.govNavy800,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  profileBtnText: {
    color: colors.slate200,
    fontSize: 12,
  },
  navBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: colors.govNavy950,
    marginTop: spacing.sm,
    paddingVertical: 6,
    paddingHorizontal: spacing.xs,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  navItem: {
    paddingVertical: 4,
    paddingHorizontal: 6,
    borderRadius: radius.sm,
  },
  navText: {
    color: colors.slate200,
    fontSize: 11,
    fontWeight: typography.weights.semibold,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.white,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    maxHeight: '75%',
    padding: spacing.lg,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  modalTitle: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  closeText: {
    fontSize: 20,
    color: colors.slate600,
    padding: 4,
  },
  modalSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginBottom: spacing.md,
  },
  langItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate100,
  },
  langItemActive: {
    backgroundColor: colors.saffron50,
    borderRadius: radius.sm,
  },
  langName: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.medium,
    color: colors.slate800,
  },
  langNameActive: {
    color: colors.saffron700,
    fontWeight: typography.weights.bold,
  },
  langNative: {
    fontSize: typography.sizes.xs,
    color: colors.slate500,
    marginTop: 2,
  },
  checkIcon: {
    fontSize: 16,
    color: colors.saffron600,
    fontWeight: 'bold',
  },
});
