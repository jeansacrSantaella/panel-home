export const $ = id => document.getElementById(id);

export const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

export const fmtTime = t => new Date(t * 1000).toLocaleString([], {day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit"});

export const dur = s => s < 60 ? s + " s" : s < 3600 ? Math.floor(s / 60) + " min" : Math.floor(s / 3600) + " h " + Math.floor(s % 3600 / 60) + " min";

export const empty = (text, tag = "p") => `<${tag} class="empty">${esc(text)}</${tag}>`;
