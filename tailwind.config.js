/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/web/templates/**/*.html"],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Noto Serif SC"', 'Georgia', 'serif'],
        sans:  ['"Noto Sans SC"', 'system-ui', 'sans-serif'],
      }
    }
  },
  plugins: [],
}
