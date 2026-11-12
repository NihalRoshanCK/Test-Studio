import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "node:path";

// Built into the Frappe app's public folder; served at /assets/test_studio/studio/.
export default defineConfig({
	plugins: [vue()],
	base: "/assets/test_studio/studio/",
	resolve: { alias: { "@": path.resolve(__dirname, "src") } },
	build: {
		outDir: "../test_studio/public/studio",
		emptyOutDir: true,
		manifest: true, // www/studio.py reads the hashed file names from .vite/manifest.json
		rollupOptions: {
			input: "src/main.js",
			output: {
				// content-hashed so chunks and the page always import the same, current entry
				entryFileNames: "studio-[hash].js",
				chunkFileNames: "chunks/[name]-[hash].js",
				assetFileNames: "assets/[name]-[hash][extname]",
			},
		},
	},
	server: { port: 8080, proxy: { "^/(api|assets|files|private|login|desk)": "http://127.0.0.1:8000" } },
});
