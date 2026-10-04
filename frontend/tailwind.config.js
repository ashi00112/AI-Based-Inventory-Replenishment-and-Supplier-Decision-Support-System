/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cyprus: {
          DEFAULT: '#014651',
          50: '#f0f9fa',
          100: '#d9f0f2',
          200: '#b5e1e5',
          700: '#025866',
          800: '#023841',
          900: '#014651',
          950: '#00252b',
        },
        malachite: {
          DEFAULT: '#03D26F',
          50: '#eefdf4',
          100: '#d6fae6',
          200: '#b0f5ce',
          400: '#2ce589',
          500: '#03D26F',
          600: '#02b35d',
          700: '#028c49',
        },
        starship: {
          DEFAULT: '#CEF431',
          200: '#e8fc8f',
          300: '#def96e',
          400: '#CEF431',
          500: '#b5dd17',
        },
        aquahaze: {
          DEFAULT: '#EAF4F4',
          50: '#f7fbfb',
          100: '#EAF4F4',
          200: '#d3e7e7',
          300: '#b8d6d6',
        },
        codgray: {
          DEFAULT: '#161514',
          800: '#262423',
          900: '#161514',
          950: '#0e0d0d',
        },
        brand: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
        }
      },
      animation: {
        'in': 'fadeSlideIn 0.2s ease-out',
      },
      keyframes: {
        fadeSlideIn: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
