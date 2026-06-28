export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          50: '#f8f8f8',
          100: '#f0f0f0',
          900: '#0a0e27',
          800: '#0f1229',
          700: '#151d3c',
          600: '#1f2847',
        },
        neon: {
          green: '#00ff41',
          blue: '#00d4ff',
          purple: '#a855f7',
          pink: '#ff006e',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
      }
    },
  },
  plugins: [],
}
