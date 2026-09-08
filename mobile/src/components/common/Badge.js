import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, radius, typography } from '../../theme/theme';

export default function Badge({ status, label, style }) {
  const getBadgeStyle = () => {
    switch (status) {
      case 'verified':
        return {
          bg: colors.emerald100,
          text: colors.emerald800,
          border: colors.emerald500,
          dot: colors.emerald600,
          displayLabel: label || 'VERIFIED',
        };
      case 'verified-ready':
      case 'verified_ready':
        return {
          bg: '#e0f2fe',
          text: '#0369a1',
          border: '#0284c7',
          dot: '#0284c7',
          displayLabel: label || 'READY FOR VERIFICATION',
        };
      case 'needs-review':
      case 'needs_review':
        return {
          bg: colors.saffron100,
          text: colors.saffron900,
          border: colors.saffron500,
          dot: colors.saffron600,
          displayLabel: label || 'NEEDS REVIEW',
        };
      case 'flagged':
        return {
          bg: colors.rose100,
          text: colors.rose800,
          border: colors.rose600,
          dot: colors.rose600,
          displayLabel: label || 'FLAGGED',
        };
      case 'processing':
        return {
          bg: '#e0e7ff',
          text: '#3730a3',
          border: '#6366f1',
          dot: '#4f46e5',
          displayLabel: label || 'PROCESSING',
        };
      default:
        return {
          bg: colors.slate100,
          text: colors.slate700,
          border: colors.slate300,
          dot: colors.slate500,
          displayLabel: label || (status ? String(status).toUpperCase() : 'UNKNOWN'),
        };
    }
  };

  const badgeTheme = getBadgeStyle();

  return (
    <View
      style={[
        styles.badge,
        { backgroundColor: badgeTheme.bg, borderColor: badgeTheme.border },
        style,
      ]}
    >
      <View style={[styles.dot, { backgroundColor: badgeTheme.dot }]} />
      <Text style={[styles.text, { color: badgeTheme.text }]}>
        {badgeTheme.displayLabel}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.full,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 5,
  },
  text: {
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.semibold,
    letterSpacing: 0.3,
  },
});
