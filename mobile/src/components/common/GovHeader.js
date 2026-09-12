import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Modal,
  FlatList,
  Image,
  Platform,
  StatusBar,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../i18n/i18n';
import { colors, radius, typography, spacing, shadows } from '../../theme/theme';
import SovereignDrawer from './SovereignDrawer';

export default function GovHeader({ title, showBack = false }) {
  const navigation = useNavigation();
  const route = useRoute();
  const { user, isAuthenticated } = useAuth();
  const { language, setLanguage, currentLangObj, languages } = useI18n();
  const [langModalOpen, setLangModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const [langSearch, setLangSearch] = useState('');

  const filteredLanguages = languages.filter((l) => {
    if (!langSearch.trim()) return true;
    const query = langSearch.toLowerCase();
    return (
      l.name.toLowerCase().includes(query) ||
      l.nativeName.toLowerCase().includes(query) ||
      l.code.toLowerCase().includes(query)
    );
  });

  return (
    <View style={styles.headerContainer}>
      <StatusBar barStyle="light-content" backgroundColor={colors.govNavy950} />

      {/* Sovereign National Top Strip */}
      <View style={styles.nationalStrip}>
        <View style={styles.nationalLeft}>
          <Text style={styles.nationalTitle}>
            GOVERNMENT OF INDIA • DILRMP (LAND RECORDS MODERNIZATION)
          </Text>
        </View>
        <View style={styles.nationalRight}>
          <View style={styles.livePulseDot} />
          <Text style={styles.nationalStatus}>Sovereign Node Active</Text>
        </View>
      </View>

      {/* Institutional Main Header Bar */}
      <View style={styles.mainBar}>
        <View style={styles.barLeft}>
          {showBack ? (
            <TouchableOpacity
              style={styles.actionBtn}
              onPress={() => navigation.goBack()}
              accessibilityLabel="Go back"
              activeOpacity={0.7}
            >
              <Ionicons name="arrow-back" size={20} color={colors.white} />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={styles.actionBtn}
              onPress={() => setDrawerOpen(true)}
              accessibilityLabel="Open navigation drawer"
              activeOpacity={0.7}
            >
              <Ionicons name="menu-outline" size={22} color={colors.white} />
            </TouchableOpacity>
          )}

          <TouchableOpacity
            style={styles.brandRow}
            onPress={() => isAuthenticated && navigation.navigate('Registry')}
            activeOpacity={0.8}
          >
            <Image
              source={require('../../../assets/images/bhoomiscan_logo.png')}
              style={styles.logoEmblem}
              resizeMode="contain"
            />
            <View style={styles.brandMeta}>
              <Text style={styles.brandTitle} numberOfLines={1}>BhoomiScan AI</Text>
              <Text style={styles.brandSubtitle} numberOfLines={1}>
                {title || 'Land Records Modernization'}
              </Text>
            </View>
          </TouchableOpacity>
        </View>

        {/* Right Header Controls - Upgraded Sovereign Language Capsule */}
        <View style={styles.barRight}>
          <TouchableOpacity
            activeOpacity={0.75}
            onPress={() => setLangModalOpen(true)}
            style={styles.langCapsule}
            accessibilityLabel="Change Language"
          >
            <View style={styles.langEmblemBadge}>
              <Text style={styles.langEmblemText}>अ/A</Text>
            </View>
            <Text style={styles.langActiveLabel}>
              {currentLangObj?.nativeName || currentLangObj?.name || 'EN'}
            </Text>
            <Ionicons name="chevron-down" size={13} color={colors.saffron400} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Sovereign Slide-Over Drawer */}
      <SovereignDrawer
        visible={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        navigation={navigation}
        currentRoute={route?.name}
      />

      {/* Upgraded 22-Language Sovereign Selection Modal */}
      <Modal
        visible={langModalOpen}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setLangModalOpen(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            {/* Modal Header */}
            <View style={styles.modalHeader}>
              <View style={styles.modalHeaderLeft}>
                <View style={styles.modalTitleRow}>
                  <View style={styles.modalEmblem}>
                    <Text style={styles.modalEmblemText}>अ/A</Text>
                  </View>
                  <Text style={styles.modalTitle}>Select Language / भाषा चुनें</Text>
                </View>
                <Text style={styles.modalSub}>
                  22 Official Schedule VIII Indian Languages (E-Governance Standard)
                </Text>
              </View>
              <TouchableOpacity
                style={styles.modalCloseBtn}
                onPress={() => {
                  setLangSearch('');
                  setLangModalOpen(false);
                }}
              >
                <Ionicons name="close" size={22} color={colors.slate600} />
              </TouchableOpacity>
            </View>

            {/* Language Quick Search Bar */}
            <View style={styles.langSearchBar}>
              <Ionicons name="search-outline" size={16} color={colors.slate400} style={{ marginRight: 8 }} />
              <TextInput
                value={langSearch}
                onChangeText={setLangSearch}
                placeholder="Search language / भाषा खोजें..."
                placeholderTextColor={colors.slate400}
                style={styles.langSearchInput}
              />
              {langSearch ? (
                <TouchableOpacity onPress={() => setLangSearch('')}>
                  <Ionicons name="close-circle" size={16} color={colors.slate400} />
                </TouchableOpacity>
              ) : null}
            </View>

            {/* Language List */}
            <FlatList
              data={filteredLanguages}
              keyExtractor={(item) => item.code}
              showsVerticalScrollIndicator={false}
              contentContainerStyle={{ paddingBottom: spacing.xl, paddingTop: 4 }}
              renderItem={({ item }) => {
                const isSelected = language === item.code;
                return (
                  <TouchableOpacity
                    style={[
                      styles.langItem,
                      isSelected && styles.langItemActive,
                    ]}
                    onPress={() => {
                      setLanguage(item.code);
                      setLangSearch('');
                      setLangModalOpen(false);
                    }}
                    activeOpacity={0.7}
                  >
                    <View style={styles.langItemLeft}>
                      <View style={styles.langItemTitleRow}>
                        <Text style={[styles.langNative, isSelected && styles.langNativeActive]}>
                          {item.nativeName}
                        </Text>
                        <View style={[styles.langCodeBadge, isSelected && styles.langCodeBadgeActive]}>
                          <Text style={[styles.langCodeText, isSelected && styles.langCodeTextActive]}>
                            {item.code.toUpperCase()}
                          </Text>
                        </View>
                      </View>
                      <Text style={[styles.langName, isSelected && styles.langNameActive]}>
                        {item.name}
                      </Text>
                    </View>
                    {isSelected ? (
                      <View style={styles.selectedCheckBadge}>
                        <Ionicons name="checkmark" size={16} color={colors.white} />
                      </View>
                    ) : (
                      <Ionicons name="chevron-forward" size={16} color={colors.slate300} />
                    )}
                  </TouchableOpacity>
                );
              }}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  headerContainer: {
    backgroundColor: colors.govNavy950,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.08)',
  },
  nationalStrip: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#020710',
    paddingHorizontal: spacing.md,
    paddingTop: Platform.OS === 'ios' ? 48 : (StatusBar.currentHeight ? StatusBar.currentHeight + 6 : 28),
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(245, 158, 11, 0.25)',
  },
  nationalLeft: {
    flex: 1,
    paddingRight: 8,
  },
  nationalTitle: {
    fontSize: 9,
    fontWeight: '800',
    color: colors.saffron500,
    letterSpacing: 0.6,
  },
  nationalRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  livePulseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.emerald500,
  },
  nationalStatus: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.emerald500,
  },
  mainBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.govNavy900,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    minHeight: 58,
  },
  barLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 10,
  },
  actionBtn: {
    width: 38,
    height: 38,
    borderRadius: radius.md,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.12)',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 10,
  },
  logoEmblem: {
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 1.5,
    borderColor: colors.saffron500,
  },
  brandMeta: {
    flex: 1,
    justifyContent: 'center',
  },
  brandTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  brandTitle: {
    color: colors.white,
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  brandSubtitle: {
    color: colors.slate400,
    fontSize: 10,
    marginTop: 2,
    fontWeight: '500',
  },
  barRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginLeft: 6,
  },
  langCapsule: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderColor: 'rgba(245, 158, 11, 0.45)',
    borderWidth: 1.2,
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: radius.full,
    ...shadows.sm,
  },
  langEmblemBadge: {
    backgroundColor: colors.saffron500,
    paddingHorizontal: 4,
    paddingVertical: 1.5,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  langEmblemText: {
    color: colors.govNavy950,
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: -0.2,
  },
  langActiveLabel: {
    color: colors.white,
    fontSize: 12,
    fontWeight: '700',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(6, 19, 37, 0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '80%',
    padding: spacing.lg,
    ...shadows.lg,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate100,
  },
  modalHeaderLeft: {
    flex: 1,
    paddingRight: 10,
  },
  modalTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  modalEmblem: {
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radius.xs,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.4)',
  },
  modalEmblemText: {
    color: colors.saffron600,
    fontSize: 11,
    fontWeight: '900',
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  modalSub: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 3,
  },
  modalCloseBtn: {
    padding: 6,
    backgroundColor: colors.slate100,
    borderRadius: radius.full,
  },
  langSearchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.slate50,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate200,
    height: 42,
    marginVertical: 10,
  },
  langSearchInput: {
    flex: 1,
    fontSize: 13,
    color: colors.govNavy900,
    paddingHorizontal: 0,
    paddingVertical: 0,
  },
  langItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radius.md,
    marginBottom: 6,
    backgroundColor: colors.slate50,
    borderWidth: 1,
    borderColor: colors.slate200,
  },
  langItemActive: {
    backgroundColor: colors.emerald50,
    borderColor: colors.emerald500,
    borderWidth: 1.5,
  },
  langItemLeft: {
    flex: 1,
  },
  langItemTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  langNative: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  langNativeActive: {
    color: colors.emerald900,
  },
  langCodeBadge: {
    backgroundColor: colors.slate200,
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: radius.xs,
  },
  langCodeBadgeActive: {
    backgroundColor: colors.emerald200,
  },
  langCodeText: {
    fontSize: 9.5,
    fontWeight: '800',
    color: colors.slate600,
  },
  langCodeTextActive: {
    color: colors.emerald800,
  },
  langName: {
    fontSize: 12,
    fontWeight: '500',
    color: colors.slate500,
    marginTop: 2,
  },
  langNameActive: {
    color: colors.emerald700,
    fontWeight: '600',
  },
  selectedCheckBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.emerald600,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
