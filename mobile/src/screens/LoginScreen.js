import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../i18n/i18n';
import { getApiBaseUrl, setCustomApiBaseUrl, loadSavedApiBaseUrl } from '../api/client';
import Input from '../components/common/Input';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import { colors, radius, typography, spacing } from '../theme/theme';

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
      setError('Please enter username and password');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await login(username.trim(), password.trim());
    } catch (err) {
      setError(err.message || 'Login failed. Please check credentials or Server URL.');
    } finally {
      setLoading(false);
    }
  };

  const setQuickCreds = (u, p) => {
    setUsername(u);
    setPassword(p);
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
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.headerBanner}>
          <TouchableOpacity
            style={styles.settingsIconBtn}
            onPress={() => setShowServerConfig(!showServerConfig)}
            activeOpacity={0.7}
          >
            <Text style={{ fontSize: 20 }}>⚙️</Text>
          </TouchableOpacity>
          <Image
            source={require('../../assets/images/BhoomiScan_AI_Logo_Icon_Transparent.png')}
            style={styles.logoLarge}
            resizeMode="contain"
          />
          <Text style={styles.title}>{t('app_title')}</Text>
          <Text style={styles.hindiTitle}>{t('app_subtitle') || 'National Land Records Digitization'}</Text>
          <Text style={styles.subtitle}>{t('app_subtitle')}</Text>
        </View>

        {showServerConfig ? (
          <Card style={[styles.card, { marginBottom: spacing.md, backgroundColor: '#0d2238', borderColor: colors.saffron500, borderWidth: 1 }]}>
            <Text style={[styles.cardHeader, { color: colors.white }]}>⚙️ Backend Server Configuration</Text>
            <Text style={[styles.cardSub, { color: colors.slate300 }]}>
              Current API Endpoint: <Text style={{ color: colors.saffron400, fontWeight: 'bold' }}>{serverUrl}</Text>
            </Text>
            <Input
              label="Custom API Base URL"
              value={serverUrl}
              onChangeText={setServerUrl}
              placeholder="http://192.168.1.113:8000/api/v1"
              autoCapitalize="none"
              style={{ backgroundColor: '#132f4c', color: colors.white }}
            />
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
              <TouchableOpacity
                style={styles.serverPresetChip}
                onPress={() => handleSaveServerUrl('http://192.168.1.113:8000/api/v1')}
              >
                <Text style={styles.serverPresetText}>Wi-Fi (192.168.1.113:8000)</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.serverPresetChip}
                onPress={() => handleSaveServerUrl('http://localhost:8000/api/v1')}
              >
                <Text style={styles.serverPresetText}>Localhost:8000</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.serverPresetChip}
                onPress={() => handleSaveServerUrl('http://10.0.2.2:8000/api/v1')}
              >
                <Text style={styles.serverPresetText}>Emulator (10.0.2.2)</Text>
              </TouchableOpacity>
            </View>
            <Button
              title="Save & Apply Server URL"
              onPress={() => handleSaveServerUrl(serverUrl)}
              variant="saffron"
              style={{ marginTop: spacing.sm }}
            />
          </Card>
        ) : null}

        <Card style={styles.card}>
          <Text style={styles.cardHeader}>{t('login_title')}</Text>
          <Text style={styles.cardSub}>{t('login_sub')}</Text>

          {error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorBoxText}>⚠️ {error}</Text>
              <Text style={{ fontSize: 11, color: colors.slate600, marginTop: 4 }}>
                Target Endpoint: {serverUrl}
              </Text>
            </View>
          ) : null}

          <Input
            label={t('username')}
            value={username}
            onChangeText={setUsername}
            placeholder="e.g. carol"
            autoCapitalize="none"
          />

          <Input
            label={t('password')}
            value={password}
            onChangeText={setPassword}
            placeholder="Enter password"
            secureTextEntry
          />

          <Button
            title={t('login_btn')}
            onPress={handleLogin}
            loading={loading}
            variant="saffron"
            style={{ marginTop: spacing.xs }}
          />

          <View style={styles.quickAccess}>
            <Text style={styles.quickAccessTitle}>Quick Access Role Logins:</Text>
            <View style={styles.quickAccessButtons}>
              <TouchableOpacity
                style={styles.quickChip}
                onPress={() => setQuickCreds('carol', 'FieldOfficer123!')}
              >
                <Text style={styles.quickChipText}>Field Officer (carol)</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.quickChip, { backgroundColor: '#1e3a5f' }]}
                onPress={() => setQuickCreds('bob', 'Verif5678!')}
              >
                <Text style={styles.quickChipText}>Verifier (bob)</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.quickChip, { backgroundColor: '#2d3748' }]}
                onPress={() => setQuickCreds('alice', 'Admin1234!')}
              >
                <Text style={styles.quickChipText}>Admin (alice)</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Card>

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            Smart India Hackathon • Sovereign Land Records Platform
          </Text>
          <Text style={styles.footerSubText}>
            DILRMP & ULPIN Standard Compliant • {serverUrl}
          </Text>
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
    padding: spacing.lg,
    justifyContent: 'center',
    minHeight: '100%',
  },
  headerBanner: {
    alignItems: 'center',
    marginBottom: spacing.xl,
    position: 'relative',
    width: '100%',
  },
  settingsIconBtn: {
    position: 'absolute',
    right: 0,
    top: 0,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  serverPresetChip: {
    backgroundColor: '#1a365d',
    borderColor: colors.saffron500,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radius.sm,
    marginBottom: 4,
  },
  serverPresetText: {
    fontSize: 11,
    color: colors.white,
    fontWeight: typography.weights.medium,
  },
  logoLarge: {
    width: 90,
    height: 90,
    marginBottom: spacing.md,
  },
  emblemContainer: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.govNavy850,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.saffron500,
    marginBottom: spacing.sm,
  },
  emblemText: {
    fontSize: 30,
  },
  title: {
    fontSize: typography.sizes.xxl,
    fontWeight: typography.weights.bold,
    color: colors.white,
    letterSpacing: 0.5,
  },
  hindiTitle: {
    fontSize: typography.sizes.sm,
    color: colors.saffron500,
    marginTop: 2,
  },
  subtitle: {
    fontSize: typography.sizes.xs,
    color: colors.slate400,
    textAlign: 'center',
    marginTop: spacing.xs,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  cardHeader: {
    fontSize: typography.sizes.lg,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  cardSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    marginBottom: spacing.lg,
  },
  errorBox: {
    backgroundColor: colors.rose50,
    borderColor: colors.rose600,
    borderWidth: 1,
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.md,
  },
  errorBoxText: {
    color: colors.rose800,
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.medium,
  },
  quickAccess: {
    marginTop: spacing.xl,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.slate200,
  },
  quickAccessTitle: {
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.semibold,
    color: colors.slate600,
    marginBottom: spacing.xs,
  },
  quickAccessButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  quickChip: {
    backgroundColor: colors.slate100,
    borderColor: colors.slate300,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radius.full,
    marginRight: 6,
    marginBottom: 6,
  },
  quickChipText: {
    fontSize: typography.sizes.xs,
    color: colors.govNavy900,
    fontWeight: typography.weights.medium,
  },
  footer: {
    marginTop: spacing.xl,
    alignItems: 'center',
  },
  footerText: {
    color: colors.slate400,
    fontSize: typography.sizes.xs,
  },
  footerSubText: {
    color: colors.slate500,
    fontSize: 10,
    marginTop: 2,
  },
});
