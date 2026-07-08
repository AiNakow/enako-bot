const path = require("path");

module.exports = {
  content: [
    path.join(__dirname, "../templates/**/*.html"),
  ],
  corePlugins: {
    preflight: true,
  },
  theme: {
    extend: {},
  },
  plugins: [],
};
