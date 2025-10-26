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
    permissions: ["tabs", "sidePanel", "storage", "<all_urls>"],
    // Broaden host permissions so content script can inject into iframes on external sites.
    // Note: <all_urls> in permissions allows some access, but host_permissions explicitly grants injection rights.
    host_permissions: [
      "http://127.0.0.1/*",
      "https://*/*",
      "http://*/*"
    ],
    options_page: "options.html",
    // action: {
    //   default_popup: "popup.html",
    // },
  },
});
