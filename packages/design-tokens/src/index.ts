export const colors = {
  background: "#0B1020",
  surface: "#121A2D",
  surfaceElevated: "#18233A",
  // Compatibility alias retained for the native client. New code should prefer
  // surfaceElevated, but both names intentionally resolve to the same token.
  surfaceRaised: "#18233A",
  text: "#F8FAFC",
  textMuted: "#A8B3C7",
  primary: "#7C9CFF",
  primaryStrong: "#5578F6",
  success: "#2BC48A",
  warning: "#F3B545",
  danger: "#F16B6B",
  border: "#2B3853",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const radius = {
  sm: 6,
  md: 10,
  lg: 16,
  pill: 999,
} as const;

export const typography = {
  fontFamilySans: "Inter",
  fontFamilyMono: "JetBrains Mono",
  size: {
    xs: 12,
    sm: 14,
    md: 16,
    lg: 20,
    xl: 28,
    xxl: 36,
  },
  lineHeight: {
    tight: 1.2,
    normal: 1.5,
    relaxed: 1.7,
  },
  // Stable semantic aliases used by React Native surfaces.
  body: 16,
  bodySmall: 14,
  label: 13,
  title: 22,
  heading: 30,
  display: 40,
} as const;

export const breakpoints = {
  phone: 0,
  tablet: 768,
  desktop: 1180,
} as const;

export const motion = {
  fast: 120,
  normal: 200,
  slow: 320,
  fastMs: 120,
  normalMs: 200,
  slowMs: 320,
} as const;

export const designTokens = {
  colors,
  spacing,
  radius,
  typography,
  breakpoints,
  motion,
} as const;
