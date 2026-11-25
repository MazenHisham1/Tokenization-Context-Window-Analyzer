import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the browser talks to Vite (port 5173) and Vite forwards /api/* to the
// Python server (port 8000). The browser sees one address, so no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  // `npm run preview` serves the production build; the end-to-end tests use it.
  preview: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "node" },
});
