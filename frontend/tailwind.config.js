/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Jersey 10', 'system-ui', 'Avenir', 'Helvetica', 'Arial', 'sans-serif'],
        jersey: ['Jersey 10', 'sans-serif'],
      },
      colors: {
        pixel: {
          dark: '#0a0a14',
          track: '#2a2a4a',
          trackLight: '#4a4a6a',
          knob: '#e8e8f0',
          knobDark: '#a0a0b0',
          amber: '#f4a020',
          amberDark: '#e89010',
        },
      },
    },
  },
  plugins: [],
}
