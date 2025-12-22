module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx}",
    "../templates/**/*.html",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'SF Pro Display',
          'SF Pro Text',
          'system-ui',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        monoSoft: ['var(--mono-font)'],
      },
    },
  },
  plugins: [],
};
