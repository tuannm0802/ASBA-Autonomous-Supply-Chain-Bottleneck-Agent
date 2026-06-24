/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Premium curated color palette (HSL-tailored feel)
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          200: '#bae2fd',
          300: '#7ccbfd',
          400: '#38b0f8',
          500: '#0ea0ea', // Primary Accent
          600: '#0280c7',
          700: '#0366a1',
          800: '#075685',
          900: '#0c486e',
          950: '#082f49',
        },
        slate: {
          850: '#151e2e',
          900: '#0f172a',
          950: '#070a13',
        }
      },
      fontFamily: {
        sans: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow': '0 0 20px rgba(14, 160, 234, 0.15)',
        'glow-strong': '0 0 30px rgba(14, 160, 234, 0.3)',
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        }
      }
    },
  },
  plugins: [],
}
