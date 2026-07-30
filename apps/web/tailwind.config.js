/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        nzassa: {
          50: '#fdf5ef',
          100: '#fae7d8',
          500: '#e07a2f',
          600: '#d1621c',
          700: '#ae4b17',
          900: '#733317'
        }
      }
    }
  },
  plugins: []
};
