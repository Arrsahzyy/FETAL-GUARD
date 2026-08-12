import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const indexHtml = fileURLToPath(new URL("./index.html", import.meta.url));

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  // Pre-bundle jspdf & autotable agar Vite tidak gagal resolve dependensinya
  optimizeDeps: {
    include: ["jspdf", "jspdf-autotable"],
  },

  build: {
    rollupOptions: {
      input: {
        app: indexHtml,
      },
      // canvg (transitive dependency jspdf) mengimpor banyak core-js polyfills.
      // Browser modern sudah support fitur-fitur ini secara native,
      // sehingga safe untuk di-external tanpa mengganggu runtime PDF export.
      external: (id) => id.startsWith("core-js/"),
    },
  },
});
