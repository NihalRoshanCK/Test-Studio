/** Tokens live as CSS variables in src/style.css so light/dark swap in one place. */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
	content: ["./src/**/*.{vue,js}"],
	darkMode: "class",
	safelist: [{ pattern: /^(bg|text)-(pass|fail|warn|run|faint)$/ }],
	theme: {
		extend: {
			colors: {
				paper: v("paper"), panel: v("panel"), menu: v("menu"), sunk: v("sunk"), line: v("line"),
				ink: v("ink"), muted: v("muted"), faint: v("faint"),
				brand: v("brand"), "brand-ink": v("brand-ink"),
				pass: v("pass"), fail: v("fail"), warn: v("warn"), rec: v("rec"), run: v("run"),
			},
			fontFamily: {
				sans: ['"Inter"', "system-ui", "sans-serif"],
				mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
			},
			fontSize: { "2xs": ["11px", "16px"], xs: ["12px", "16px"], sm: ["13px", "20px"], base: ["14px", "22px"], lg: ["16px", "24px"], xl: ["20px", "28px"], "2xl": ["26px", "32px"] },
			borderRadius: { DEFAULT: "6px", md: "8px", lg: "10px" },
			boxShadow: { pop: "0 1px 2px rgb(16 24 40 / .06), 0 8px 24px -6px rgb(16 24 40 / .16)" },
		},
	},
};
