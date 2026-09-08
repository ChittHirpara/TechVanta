import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useAuth } from '../../context/AuthContext';
import { colors, radius, typography, spacing } from '../../theme/theme';

export default function GovHeader() {
  const { user, isAuthenticated, logout } = useAuth();

  const roleLabels = {
    admin: 'Administrator',
    verifier: 'Verifying Officer',
    field_officer: 'Field Officer',
  };

  return (
    <View style={styles.header}>
      <View style={styles.topRow}>
        <View style={styles.brandRow}>
          <View style={styles.emblemBadge}>
            <Text style={styles.emblemIcon}>🏛️</Text>
          </View>
          <View style={styles.brandTitleContainer}>
            <Text style={styles.brandTitle}>BhoomiScan AI</Text>
            <Text style={styles.brandSub}>Sovereign Land Digitization</Text>
          </View>
        </View>
        {isAuthenticated ? (
          <TouchableOpacity activeOpacity={0.8} onPress={logout} style={styles.signOutBtn}>
            <Text style={styles.signOutText}>Sign Out</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      {isAuthenticated && user ? (
        <View style={styles.userStrip}>
          <Text style={styles.userName}>
            👤 {user.full_name || user.username}
          </Text>
          <View style={styles.roleBadge}>
            <Text style={styles.roleText}>
              {roleLabels[user.role] || user.role}
            </Text>
          </View>
        </View>
      ) : null}
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
  },
  emblemBadge: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.govNavy800,
    alignItems: 'center',
    justify: 'center',
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
    fontSize: typography.sizes.xs,
  },
  signOutBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.25)',
  },
  signOutText: {
    color: colors.slate300,
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.medium,
  },
  userStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    justify: 'space-between',
    marginTop: spacing.sm,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.08)',
  },
  userName: {
    color: colors.slate200,
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.medium,
  },
  roleBadge: {
    backgroundColor: colors.saffron900,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.saffron600,
  },
  roleText: {
    color: colors.saffron100,
    fontSize: 10,
    fontWeight: typography.weights.bold,
    textTransform: 'uppercase',
  },
});
