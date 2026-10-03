export const TYPOGRAPHY = {
  display: {
    size: 'clamp(2.5rem, 8vw, 4.5rem)',
    weight: 700,
    lineHeight: 1.1,
    letterSpacing: '-0.02em',
    family: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  },
  heading: {
    size: 'clamp(1.5rem, 4vw, 2.25rem)',
    weight: 600,
    lineHeight: 1.2,
    letterSpacing: '-0.01em',
    family: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  },
  subheading: {
    size: '1.125rem',
    weight: 600,
    lineHeight: 1.3,
    letterSpacing: '-0.005em',
    family: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  },
  body: {
    size: '1rem',
    weight: 400,
    lineHeight: 1.6,
    letterSpacing: '0em',
    family: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  },
  metadata: {
    size: '0.875rem',
    weight: 500,
    lineHeight: 1.4,
    letterSpacing: '0.01em',
    family: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  },
  caption: {
    size: '0.75rem',
    weight: 500,
    lineHeight: 1.4,
    letterSpacing: '0.03em',
    family: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  },
  mono: {
    size: '0.875rem',
    weight: 400,
    lineHeight: 1.5,
    letterSpacing: '0em',
    family: '"JetBrains Mono", "Fira Code", monospace'
  }
} as const;
