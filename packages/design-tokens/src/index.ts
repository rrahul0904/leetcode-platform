export const colors = {
  background: "#0B1020",
  surface: "#121A2E",
  surfaceRaised: "#18233D",
  text: "#F7F9FC",
  textMuted: "#A9B4C8",
  primary: "#8FA8FF",
  primaryStrong: "#6F8FFF",
  success: "#61D095",
  warning: "#F6C85F",
  danger: "#FF7A8A",
  border: "#273554",
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
  sm: 8,
  md: 12,
  lg: 18,
  pill: 999,
} as const;

export const typography = {
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
  fastMs: 120,
  normalMs: 200,
  slowMs: 320,
} as const;
