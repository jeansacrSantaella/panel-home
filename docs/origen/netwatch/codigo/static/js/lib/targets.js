const COLORS = {gateway: "var(--up)", "1.1.1.1": "#3a6ea5", "8.8.8.8": "#a0602a"};
const NAMES = {gateway: "Router (red local)", "1.1.1.1": "Cloudflare 1.1.1.1", "8.8.8.8": "Google 8.8.8.8"};

export const targetColor = key => COLORS[key] || "var(--ink)";
export const targetName = key => NAMES[key] || key;
