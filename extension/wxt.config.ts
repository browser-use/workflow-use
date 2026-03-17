// wxt.config.ts
import { defineConfig } from "wxt";
import baseViteConfig from "./vite.config";

import { mergeConfig } from "vite";

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  srcDir: "src",
  vite: () =>
    mergeConfig(baseViteConfig, {
      // WXT-specific overrides (optional)
    }),
  manifest: {
    permissions: ["tabs", "sidePanel", "storage", "scripting", "activeTab", "<all_urls>"],
    host_permissions: ["http://127.0.0.1/*", "http://localhost/*"],
    // options_page: "options.html",
    // action: {
    //   default_popup: "popup.html",
    // },
  },
});
