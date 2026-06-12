export interface CoreStatus {
  ok: boolean;
  status?: number;
  error?: string;
  body?: Record<string, unknown>;
}

export interface Subscription {
  id: string;
  name: string;
  url_masked: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  last_error: string | null;
  node_count: number;
}

export interface NodeItem {
  id: string;
  name: string;
  type: string;
  server: string;
  port: number | string;
  subscription_id: string;
  subscription_name: string;
}

export interface NodeDelayResult {
  node_id: string;
  name?: string;
  subscription_id?: string;
  subscription_name?: string;
  tested_at: string;
  ok: boolean;
  alive: boolean;
  delay_ms: number | null;
  error?: string;
}

export type BindingMode = "builtin" | "node";

export interface Binding {
  port: number;
  mode: BindingMode;
  enabled: boolean;
  listen: string;
  updated_at?: string;
  host_proxy: string;
  container_proxy: string;
  target?: string;
  label: string;
  resolved: boolean;
  subscription_id?: string;
  node_id?: string;
}

export interface SystemProxyHelperState extends ApiEnvelope {
  enabled?: boolean;
  server?: string;
  override?: string;
  status?: number;
  supported?: boolean;
  backend?: string;
  platform?: string;
}

export interface SystemProxyState {
  enabled: boolean;
  desired_enabled: boolean;
  server: string;
  server_port: number;
  bypass: string;
  default_bypass: string;
  helper_ok: boolean;
  helper: SystemProxyHelperState;
  selected_subscription_id: string | null;
  selected_node_id: string | null;
  selected_label: string | null;
  selected_resolved: boolean;
  updated_at: string | null;
}

export interface GatewayState {
  port_min: number;
  port_max: number;
  subscriptions: Subscription[];
  bindings: Binding[];
  system_proxy: SystemProxyState;
  core: CoreStatus;
}

export interface ApiEnvelope {
  ok?: boolean;
  error?: string;
}

export interface ProbeAttempt extends ApiEnvelope {
  target_url?: string | null;
  proxy?: string;
  status?: number;
  elapsed_ms: number;
  body?: string;
}

export interface CreateSubscriptionResponse extends ApiEnvelope {
  subscription: Subscription;
}

export interface NodeListResponse extends ApiEnvelope {
  nodes: NodeItem[];
  count: number;
}

export interface ProbeResponse extends ApiEnvelope {
  target_url?: string | null;
  proxy?: string;
  status?: number;
  elapsed_ms: number;
  body?: string;
  attempts?: ProbeAttempt[];
}

export interface SystemProxyResponse extends ApiEnvelope {
  system_proxy: SystemProxyState;
}

export interface SystemProxySettingsPayload {
  server_port: number;
  bypass: string;
}

export interface SystemProxyProbeResponse extends ProbeResponse {
  target_url?: string;
  proxy?: string;
}

export interface NodeDelayResponse extends ApiEnvelope {
  subscription_id: string;
  tested_url: string;
  timeout_ms: number;
  count: number;
  ok_count: number;
  results: NodeDelayResult[];
}

export interface BindingPayload {
  port: number;
  target?: string;
  subscription_id?: string;
  node_id?: string;
}
