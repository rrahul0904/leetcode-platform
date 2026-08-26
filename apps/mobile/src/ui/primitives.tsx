import { colors, radius, spacing, typography } from "@rigor/design-tokens";
import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from "react-native";

export function Screen({
  children,
  scroll = true,
  contentStyle,
}: {
  children: ReactNode;
  scroll?: boolean;
  contentStyle?: ViewStyle;
}) {
  const content = <View style={[styles.screenContent, contentStyle]}>{children}</View>;
  return (
    <SafeAreaView style={styles.safeArea}>
      {scroll ? (
        <ScrollView contentContainerStyle={styles.scrollContent}>{content}</ScrollView>
      ) : (
        content
      )}
    </SafeAreaView>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <Text style={styles.eyebrow}>{children}</Text>;
}

export function PageTitle({ title, description }: { title: string; description?: string }) {
  return (
    <View style={styles.titleBlock}>
      <Text accessibilityRole="header" style={styles.pageTitle}>
        {title}
      </Text>
      {description ? <Text style={styles.description}>{description}</Text> : null}
    </View>
  );
}

export function Card({ children }: { children: ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <Text style={styles.sectionTitle}>{children}</Text>;
}

export function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <View style={styles.metric} accessibilityLabel={`${label}: ${value}`}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
      {detail ? <Text style={styles.metricDetail}>{detail}</Text> : null}
    </View>
  );
}

export function Tag({ children }: { children: ReactNode }) {
  return (
    <View style={styles.tag}>
      <Text style={styles.tagText}>{children}</Text>
    </View>
  );
}

export function PrimaryButton({
  label,
  onPress,
  disabled = false,
  busy = false,
  variant = "primary",
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "secondary" | "danger";
}) {
  const buttonStyle =
    variant === "secondary"
      ? styles.buttonSecondary
      : variant === "danger"
        ? styles.buttonDanger
        : styles.buttonPrimary;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled, busy }}
      disabled={disabled || busy}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        buttonStyle,
        (disabled || busy) && styles.buttonDisabled,
        pressed && !(disabled || busy) && styles.buttonPressed,
      ]}
    >
      {busy ? <ActivityIndicator color={colors.background} /> : null}
      <Text style={variant === "secondary" ? styles.buttonTextSecondary : styles.buttonText}>
        {label}
      </Text>
    </Pressable>
  );
}

export function StateMessage({
  title,
  detail,
  loading = false,
}: {
  title: string;
  detail?: string;
  loading?: boolean;
}) {
  return (
    <View style={styles.stateMessage} accessibilityRole={loading ? undefined : "alert"}>
      {loading ? <ActivityIndicator color={colors.primary} /> : null}
      <Text style={styles.stateTitle}>{title}</Text>
      {detail ? <Text style={styles.stateDetail}>{detail}</Text> : null}
    </View>
  );
}

export const mobileStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  rowWrap: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  stack: {
    gap: spacing.md,
  },
  muted: {
    color: colors.textMuted,
  },
  body: {
    color: colors.text,
    fontSize: typography.body,
    lineHeight: 24,
  },
  small: {
    color: colors.textMuted,
    fontSize: typography.bodySmall,
    lineHeight: 20,
  },
});

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
  },
  screenContent: {
    flex: 1,
    width: "100%",
    maxWidth: 1100,
    alignSelf: "center",
    padding: spacing.lg,
    gap: spacing.lg,
  },
  eyebrow: {
    color: colors.primary,
    fontWeight: "700",
    fontSize: typography.label,
    letterSpacing: 1.2,
  },
  titleBlock: {
    gap: spacing.sm,
  },
  pageTitle: {
    color: colors.text,
    fontWeight: "800",
    fontSize: typography.heading,
    lineHeight: 38,
  },
  description: {
    color: colors.textMuted,
    fontSize: typography.body,
    lineHeight: 24,
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: typography.title,
    fontWeight: "700",
  },
  metric: {
    minWidth: 120,
    flexGrow: 1,
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs,
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: typography.label,
    fontWeight: "600",
  },
  metricValue: {
    color: colors.text,
    fontSize: typography.title,
    fontWeight: "800",
  },
  metricDetail: {
    color: colors.textMuted,
    fontSize: typography.label,
  },
  tag: {
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    alignSelf: "flex-start",
  },
  tagText: {
    color: colors.textMuted,
    fontSize: typography.label,
    fontWeight: "600",
  },
  button: {
    minHeight: 48,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacing.sm,
  },
  buttonPrimary: {
    backgroundColor: colors.primary,
  },
  buttonSecondary: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceRaised,
  },
  buttonDanger: {
    backgroundColor: colors.danger,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonPressed: {
    opacity: 0.82,
  },
  buttonText: {
    color: colors.background,
    fontWeight: "800",
    fontSize: typography.body,
  },
  buttonTextSecondary: {
    color: colors.text,
    fontWeight: "800",
    fontSize: typography.body,
  },
  stateMessage: {
    minHeight: 180,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.sm,
  },
  stateTitle: {
    color: colors.text,
    fontSize: typography.title,
    fontWeight: "700",
    textAlign: "center",
  },
  stateDetail: {
    color: colors.textMuted,
    fontSize: typography.body,
    textAlign: "center",
    lineHeight: 24,
  },
});
