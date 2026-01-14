module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx}",
    "../shared-ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--body-font)"],
        title: ["var(--title-font)"],
        monoSoft: ["var(--mono-font)"],
      },
    },
  },
  plugins: [],
};
