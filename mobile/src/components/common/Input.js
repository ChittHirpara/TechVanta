import React from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';
import { colors, radius, typography, spacing } from '../../theme/theme';

export default function Input({
  label,
  value,
  onChangeText,
  placeholder,
  secureTextEntry,
  keyboardType,
  autoCapitalize = 'none',
  error,
  multiline,
  numberOfLines,
  style,
  inputStyle,
}) {
  return (
    <View style={[styles.container, style]}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.slate400}
        secureTextEntry={secureTextEntry}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        multiline={multiline}
        numberOfLines={numberOfLines}
        style={[
          styles.input,
          error ? styles.inputError : null,
          multiline && { height: (numberOfLines || 3) * 24, textAlignVertical: 'top' },
          inputStyle,
        ]}
      />
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.md,
  },
  label: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.semibold,
    color: colors.slate700,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.bgCard,
    borderColor: colors.borderCard,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: typography.sizes.md,
    color: colors.slate900,
  },
  inputError: {
    borderColor: colors.rose600,
  },
  errorText: {
    fontSize: typography.sizes.xs,
    color: colors.rose600,
    marginTop: 4,
  },
});
