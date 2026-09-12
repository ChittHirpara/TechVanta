import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  Image,
  StatusBar,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../i18n/i18n';
import { getApiBaseUrl, setCustomApiBaseUrl, loadSavedApiBaseUrl } from '../api/client';
import Input from '../components/common/Input';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import { colors, radius, typography, spacing, shadows } from '../theme/theme';

export default function LoginScreen({ route }) {
  const { login } = useAuth();
  const { t } = useI18n();
  const sessionExpiredMsg = route?.params?.message;
  const [username, setUsername] = useState('carol');
  const [password, setPassword] = useState('FieldOfficer123!');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(sessionExpiredMsg || null);
  const [serverUrl, setServerUrl] = useState(getApiBaseUrl());
  const [showServerConfig, setShowServerConfig] = useState(false);

  useEffect(() => {
    loadSavedApiBaseUrl().then((url) => {
      if (url) setServerUrl(url);
    });
  }, []);

  const handleLogin = async () => {
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username and password');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await login(username.trim(), password.trim());
    } catch (err) {
      setError(err.message || 'Login failed. Please verify your backend server connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleFillDemoCreds = () => {
    setUsername('carol');
    setPassword('FieldOfficer123!');
    setError(null);
  };

  const handleSaveServerUrl = async (newUrl) => {
    await setCustomApiBaseUrl(newUrl);
    setServerUrl(getApiBaseUrl());
    setError(null);
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <StatusBar barStyle="light-content" backgroundColor={colors.govNavy950} />
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* Top Header & Sovereign Emblem Logo */}
        <View style={styles.headerBanner}>
          <TouchableOpacity
            style={styles.settingsIconBtn}
            onPress={() => setShowServerConfig(!showServerConfig)}
            activeOpacity={0.7}
            accessibilityLabel="Configure server URL"
          >
            <Text style={{ fontSize: 18 }}>⚙️</Text>
          </TouchableOpacity>

          {/* Logo with Sovereign Ring Accent */}
          <View style={styles.logoWrapper}>
            <Image
              source={require('../../assets/images/bhoomiscan_logo.png')}
              style={styles.logoImage}
              resizeMode="contain"
            />
          </View>

          <Text style={styles.brandTitle}>BhoomiScan AI</Text>
          <View style={styles.sovereignBadge}>
            <Text style={styles.sovereignBadgeText}>🇮🇳 DILRMP • SOVEREIGN GOVERNANCE</Text>
          </View>
          <Text style={styles.roleSubtext}>Field Officer Land Record Digitization</Text>
        </View>

        {/* Optional Server Configuration Panel */}
        {showServerConfig && (
          <Card style={styles.serverConfigCard}>
            <View style={styles.serverConfigHeader}>
              <Text style={styles.serverConfigTitle}>⚙️ Backend Server Configuration</Text>
              <TouchableOpacity onPress={() => setShowServerConfig(false)}>
                <Text style={{ color: colors.slate400, fontSize: 16 }}>✕</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.serverConfigDesc}>
              Active Target: <Text style={{ color: colors.saffron400, fontWeight: '700' }}>{serverUrl}</Text>
            </Text>

            <Input
              label="Backend Endpoint URL"
              value={serverUrl}
              onChangeText={setServerUrl}
              placeholder="http://10.143.194.49:8000/api/v1"
              autoCapitalize="none"
              style={{ backgroundColor: colors.govNavy900, color: colors.white, borderColor: colors.govNavy700 }}
            />

            <Text style={styles.presetLabel}>Quick Presets:</Text>
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
              title="Save & Apply Endpoint"
              onPress={() => handleSaveServerUrl(serverUrl)}
              variant="saffron"
              style={{ marginTop: spacing.sm }}
            />
          </Card>
        )}

        {/* Main Authentication Card */}
        <View style={styles.authCard}>
          <View style={styles.authCardHeader}>
            <Text style={styles.cardHeader}>Field Officer Login</Text>
            <Text style={styles.cardSub}>Sign in with your assigned field officer credentials</Text>
          </View>

          {error ? (
            <View style={styles.errorBox}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <Ionicons name="alert-circle" size={16} color={colors.rose600} />
                <Text style={styles.errorTitle}>Connection & Auth Alert</Text>
              </View>
              <Text style={styles.errorBoxText}>{error}</Text>
              <Text style={styles.errorEndpoint}>Endpoint: {serverUrl}</Text>
            </View>
          ) : null}

          <View style={styles.formGroup}>
            <Input
              label="Username / Officer ID"
              value={username}
              onChangeText={setUsername}
              placeholder="e.g. carol"
              autoCapitalize="none"
            />

            <Input
              label="Password"
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••••••"
              secureTextEntry
            />

            <Button
              title={loading ? "Authenticating..." : "Authenticate Field Officer"}
              onPress={handleLogin}
              loading={loading}
              variant="saffron"
              style={styles.submitBtn}
            />
          </View>

          {/* Clean Demo Autofill Pill */}
          <View style={styles.demoSection}>
            <TouchableOpacity
              style={styles.demoButton}
              onPress={handleFillDemoCreds}
              activeOpacity={0.7}
            >
              <Text style={styles.demoButtonIcon}>⚡</Text>
              <Text style={styles.demoButtonText}>Auto-fill Demo Credentials (carol)</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Institutional Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerBrand}>Smart India Hackathon • Sovereign Land Records Platform</Text>
          <Text style={styles.footerSub}>Department of Land Resources (DoLR) • DILRMP & Bhu-Aadhaar Compliant</Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.govNavy950,
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
    paddingTop: Platform.OS === 'ios' ? spacing.xxl : spacing.xl,
    paddingBottom: spacing.xxl,
    justifyContent: 'center',
    minHeight: '100%',
  },
  headerBanner: {
    alignItems: 'center',
    marginBottom: spacing.lg,
    position: 'relative',
    width: '100%',
  },
  settingsIconBtn: {
    position: 'absolute',
    right: 0,
    top: 0,
    width: 38,
    height: 38,
    borderRadius: radius.full,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
    zIndex: 10,
  },
  logoWrapper: {
    width: 104,
    height: 104,
    borderRadius: radius.full,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
    borderWidth: 3,
    borderColor: colors.saffron500,
    ...shadows.lg,
    overflow: 'hidden',
  },
  logoImage: {
    width: 96,
    height: 96,
  },
  brandTitle: {
    fontSize: 26,
    fontWeight: '800',
    color: colors.white,
    letterSpacing: 0.5,
  },
  sovereignBadge: {
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    borderColor: colors.saffron500,
    borderWidth: 1,
    borderRadius: radius.full,
    paddingHorizontal: 12,
    paddingVertical: 3,
    marginTop: 6,
    marginBottom: 4,
  },
  sovereignBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.saffron400,
    letterSpacing: 0.6,
  },
  roleSubtext: {
    fontSize: 13,
    color: colors.slate300,
    fontWeight: '500',
    marginTop: 2,
  },
  serverConfigCard: {
    backgroundColor: colors.govNavy900,
    borderColor: colors.saffron500,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    ...shadows.md,
  },
  serverConfigHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  serverConfigTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.white,
  },
  serverConfigDesc: {
    fontSize: 12,
    color: colors.slate300,
    marginBottom: spacing.sm,
  },
  presetLabel: {
    fontSize: 11,
    color: colors.slate400,
    fontWeight: '600',
    marginTop: spacing.xs,
    marginBottom: 4,
  },
  presetRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: spacing.xs,
  },
  presetChip: {
    backgroundColor: colors.govNavy800,
    borderColor: 'rgba(255, 255, 255, 0.15)',
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radius.sm,
  },
  presetChipText: {
    fontSize: 11,
    color: colors.slate200,
    fontWeight: '500',
  },
  authCard: {
    backgroundColor: colors.white,
    borderRadius: 20,
    padding: spacing.lg,
    ...shadows.lg,
  },
  authCardHeader: {
    marginBottom: spacing.md,
  },
  cardHeader: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.govNavy950,
    letterSpacing: -0.2,
  },
  cardSub: {
    fontSize: 12,
    color: colors.slate500,
    marginTop: 3,
  },
  formGroup: {
    marginTop: spacing.xs,
  },
  submitBtn: {
    marginTop: spacing.sm,
    borderRadius: radius.md,
    height: 48,
  },
  errorBox: {
    backgroundColor: '#fff1f2',
    borderColor: '#f43f5e',
    borderWidth: 1,
    padding: spacing.sm,
    borderRadius: radius.md,
    marginBottom: spacing.md,
  },
  errorTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#9f1239',
    marginBottom: 2,
  },
  errorBoxText: {
    color: '#be123c',
    fontSize: 12,
    fontWeight: '500',
    lineHeight: 16,
  },
  errorEndpoint: {
    fontSize: 10,
    color: colors.slate500,
    marginTop: 4,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  demoSection: {
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.slate100,
    alignItems: 'center',
  },
  demoButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.govNavy50,
    borderColor: colors.govNavy100,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.full,
  },
  demoButtonIcon: {
    fontSize: 13,
    marginRight: 6,
  },
  demoButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.govNavy700,
  },
  footer: {
    marginTop: spacing.xl,
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
  },
  footerBrand: {
    color: colors.slate400,
    fontSize: 11,
    fontWeight: '600',
    textAlign: 'center',
  },
  footerSub: {
    color: colors.slate500,
    fontSize: 10,
    textAlign: 'center',
    marginTop: 3,
  },
});
