import { reactive, ref } from "vue";

import type { ViewKey } from "@/router/views";
import type { BindingMode, GatewayState, NodeDelayResult, NodeItem, SystemProxyProbeResponse } from "@/types/gateway";
import type { NodeSortMode } from "@/types/ui";

export function createGatewayState() {
  const activeView = ref<ViewKey>("dashboard");
  const stateData = ref<GatewayState | null>(null);
  const selectedSubscriptionId = ref<string | null>(null);
  const nodes = ref<NodeItem[]>([]);
  const selectedNode = ref<NodeItem | null>(null);
  const nodeQuery = ref("");
  const typeFilter = ref("all");
  const nodeSort = ref<NodeSortMode>("default");
  const bindingMode = ref<BindingMode>("node");
  const builtinTarget = ref("AUTO");
  const bindingPort = ref(7900);
  const systemProxySubscriptionId = ref<string | null>(null);
  const systemProxyNodes = ref<NodeItem[]>([]);
  const systemProxySelectedNode = ref<NodeItem | null>(null);
  const systemProxyQuery = ref("");
  const systemProxyTypeFilter = ref("all");
  const systemProxySort = ref<NodeSortMode>("default");
  const settingsProxyPort = ref(7896);
  const settingsBypassText = ref("");

  const loadingState = ref(false);
  const loadingNodes = ref(false);
  const loadingSystemProxyNodes = ref(false);
  const creatingSubscription = ref(false);
  const refreshingId = ref<string | null>(null);
  const savingBinding = ref(false);
  const rebuilding = ref(false);
  const probingPort = ref<number | null>(null);
  const testingDelays = ref(false);
  const testingSystemProxyDelays = ref(false);
  const savingSystemProxy = ref(false);
  const savingSystemProxySettings = ref(false);
  const probingSystemProxy = ref(false);
  const nodeDelayResults = ref<Record<string, NodeDelayResult>>({});
  const systemProxyProbeResult = ref<SystemProxyProbeResponse | null>(null);

  const subscriptionForm = reactive({
    name: "",
    url: "",
  });

  const builtinTargets = ["AUTO", "NODE", "DIRECT", "GLOBAL", "REJECT"];

  return {
    activeView,
    stateData,
    selectedSubscriptionId,
    nodes,
    selectedNode,
    nodeQuery,
    typeFilter,
    nodeSort,
    bindingMode,
    builtinTarget,
    bindingPort,
    systemProxySubscriptionId,
    systemProxyNodes,
    systemProxySelectedNode,
    systemProxyQuery,
    systemProxyTypeFilter,
    systemProxySort,
    settingsProxyPort,
    settingsBypassText,
    loadingState,
    loadingNodes,
    loadingSystemProxyNodes,
    creatingSubscription,
    refreshingId,
    savingBinding,
    rebuilding,
    probingPort,
    testingDelays,
    testingSystemProxyDelays,
    savingSystemProxy,
    savingSystemProxySettings,
    probingSystemProxy,
    nodeDelayResults,
    systemProxyProbeResult,
    subscriptionForm,
    builtinTargets,
  };
}

export type GatewayManagerState = ReturnType<typeof createGatewayState>;
