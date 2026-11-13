// Centraliza las URLs y las llamadas a la API.
async function request(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

const post = (url, body) => request(url, {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify(body),
});

export const api = {
  summary: () => request("/api/summary"),
  events: params => request(`/api/events?${new URLSearchParams(params)}`),
  setAlias: (mac, alias) => post("/api/alias", {mac, alias}),
  setNetwork: (mac, network) => post("/api/network", {mac, network}),
  scan: (host, ports) => post("/api/scan", {host, ports}),
};
