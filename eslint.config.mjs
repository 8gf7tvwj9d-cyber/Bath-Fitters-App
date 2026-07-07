import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: ["node_modules/**", ".venv/**", "instance/**", "__pycache__/**"],
  },
  {
    files: ["assets/app.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        ...globals.browser,
        ...globals.es2024,
        BarcodeDetector: "readonly",
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      "no-alert": "off",
      "no-unused-vars": "off",
    },
  },
];
