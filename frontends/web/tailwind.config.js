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
      animation: {
        'fade-in-out': 'fadeInOut 3s ease-in-out forwards',
      },
      keyframes: {
        fadeInOut: {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '10%':  { opacity: '1', transform: 'translateY(0)' },
          '80%':  { opacity: '1' },
          '100%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}

