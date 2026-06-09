import type {
  BindingPayload,
  CreateSubscriptionResponse,
  GatewayState,
  NodeDelayResponse,
  NodeListResponse,
  ProbeResponse,
  SystemProxyProbeResponse,
  SystemProxyResponse,
  SystemProxySettingsPayload,
} from "@/types/gateway";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const text = await response.text();
  let payload: unknown = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { error: text };
  }

  const error = payload && typeof payload === "object" && "error" in payload ? String(payload.error) : "";
  const ok = payload && typeof payload === "object" && "ok" in payload ? Boolean(payload.ok) : true;
  if (!response.ok || ok === false) {
    throw new Error(error || `HTTP ${response.status}`);
  }
  return payload as T;
}

export function getState() {
  return request<GatewayState>("/api/state");
}

export function createSubscription(payload: { name?: string; url: string }) {
  return request<CreateSubscriptionResponse>("/api/subscriptions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getNodes(subscriptionId: string) {
  return request<NodeListResponse>(`/api/subscriptions/${encodeURIComponent(subscriptionId)}/nodes`);
}

export function testNodeDelays(subscriptionId: string, nodeId?: string) {
  return request<NodeDelayResponse>(`/api/subscriptions/${encodeURIComponent(subscriptionId)}/nodes/delay`, {
    method: "POST",
    body: JSON.stringify(nodeId ? { node_id: nodeId } : {}),
  });
}

export function refreshSubscription(subscriptionId: string) {
  return request(`/api/subscriptions/${encodeURIComponent(subscriptionId)}/refresh`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function deleteSubscription(subscriptionId: string) {
  return request(`/api/subscriptions/${encodeURIComponent(subscriptionId)}`, {
    method: "DELETE",
  });
}

export function saveBinding(payload: BindingPayload) {
  return request("/api/bindings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteBinding(port: number) {
  return request(`/api/bindings/${port}`, {
    method: "DELETE",
  });
}

export function rebuildConfig() {
  return request("/api/rebuild", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function probePort(port: number) {
  return request<ProbeResponse>("/api/probe", {
    method: "POST",
    body: JSON.stringify({ port }),
  });
}

export function getSystemProxy() {
  return request<SystemProxyResponse>("/api/system-proxy");
}

export function updateSystemProxy(payload: { enabled: boolean }) {
  return request<SystemProxyResponse>("/api/system-proxy", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSystemProxySettings(payload: SystemProxySettingsPayload) {
  return request<SystemProxyResponse>("/api/system-proxy/settings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function selectSystemProxyNode(payload: { subscription_id: string; node_id: string }) {
  return request<SystemProxyResponse>("/api/system-proxy/node", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function probeSystemProxy() {
  return request<SystemProxyProbeResponse>("/api/system-proxy/probe", {
    method: "POST",
    body: JSON.stringify({}),
  });
}
