import React, { useState } from 'react';
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
import Input from '../components/common/Input';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import { colors, radius, typography, spacing } from '../theme/theme';

export default function LoginScreen({ route }) {
  const { login } = useAuth();
  const sessionExpiredMsg = route?.params?.message;
  const [username, setUsername] = useState('field_officer');
  const [password, setPassword] = useState('officer123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(sessionExpiredMsg || null);

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
      setError(err.message || 'Login failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  const setQuickCreds = (u, p) => {
    setUsername(u);
    setPassword(p);
    setError(null);
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.headerBanner}>
          <View style={styles.emblemContainer}>
            <Text style={styles.emblemText}>🏛️</Text>
          </View>
          <Text style={styles.title}>BhoomiScan AI</Text>
          <Text style={styles.hindiTitle}>भूमिस्कैन एआई - भू-अभिलेख क्षेत्र अधिकारी</Text>
          <Text style={styles.subtitle}>
            Field Officer Mobile App • Capture, Local Queue & Status Tracking
          </Text>
        </View>

        <Card style={styles.card}>
          <Text style={styles.cardHeader}>Field Officer Authentication</Text>
          <Text style={styles.cardSub}>Sign in with your assigned field officer credentials</Text>

          {error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorBoxText}>⚠️ {error}</Text>
            </View>
          ) : null}

          <Input
            label="Field Officer Username"
            value={username}
            onChangeText={setUsername}
            placeholder="e.g. field_officer"
            autoCapitalize="none"
          />

          <Input
            label="Password"
            value={password}
            onChangeText={setPassword}
            placeholder="Enter password"
            secureTextEntry
          />

          <Button
            title="Authenticate Field Officer"
            onPress={handleLogin}
            loading={loading}
            variant="saffron"
            style={{ marginTop: spacing.xs }}
          />

          <View style={styles.quickAccess}>
            <Text style={styles.quickAccessTitle}>Quick Field Officer Credentials:</Text>
            <View style={styles.quickAccessButtons}>
              <TouchableOpacity
                style={styles.quickChip}
                onPress={() => setQuickCreds('field_officer', 'officer123')}
              >
                <Text style={styles.quickChipText}>Field Officer (`field_officer`)</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Card>

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            Smart India Hackathon • Sovereign Land Records Platform
          </Text>
          <Text style={styles.footerSubText}>
            DILRMP & ULPIN Standard Compliant
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
