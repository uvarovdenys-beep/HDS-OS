export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        dark: { 900: '#0a0e27', 800: '#0f1229', 700: '#151d3c' },
        neon: { green: '#00ff41', blue: '#00d4ff', purple: '#a855f7' }
      },
      fontFamily: { mono: ['JetBrains Mono', 'monospace'] }
    }
  }
}
