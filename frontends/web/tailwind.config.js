/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        background: '#020617',   // slate-950
        surface:    '#0f172a',   // slate-900
        border:     '#1e293b',   // slate-800
      },
    },
  },
  plugins: [],
}

