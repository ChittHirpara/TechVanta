import React from 'react';
import { TouchableOpacity, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { colors, radius, typography, spacing } from '../../theme/theme';

export default function Button({
  title,
  onPress,
  variant = 'primary', // 'primary', 'saffron', 'secondary', 'outline', 'danger'
  loading = false,
  disabled = false,
  style,
  textStyle,
  icon,
}) {
  const getVariantStyles = () => {
    switch (variant) {
      case 'saffron':
        return {
          bg: colors.saffron600,
          text: colors.white,
          border: colors.saffron600,
        };
      case 'secondary':
        return {
          bg: colors.govNavy800,
          text: colors.white,
          border: colors.govNavy800,
        };
      case 'outline':
        return {
          bg: 'transparent',
          text: colors.govNavy900,
          border: colors.slate300,
        };
      case 'danger':
        return {
          bg: colors.rose600,
          text: colors.white,
          border: colors.rose600,
        };
      case 'primary':
      default:
        return {
          bg: colors.govNavy600,
          text: colors.white,
          border: colors.govNavy600,
        };
    }
  };

  const vStyle = getVariantStyles();
  const isDisabled = disabled || loading;

  return (
    <TouchableOpacity
      activeOpacity={0.8}
      onPress={onPress}
      disabled={isDisabled}
      style={[
        styles.button,
        { backgroundColor: vStyle.bg, borderColor: vStyle.border },
        isDisabled && styles.disabledButton,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={vStyle.text} size="small" />
      ) : (
        <>
          {icon}
          <Text style={[styles.text, { color: vStyle.text }, icon && { marginLeft: 8 }, textStyle]}>
            {title}
          </Text>
        </>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    borderWidth: 1,
    minHeight: 46,
  },
  disabledButton: {
    opacity: 0.55,
  },
  text: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.semibold,
    textAlign: 'center',
  },
});
