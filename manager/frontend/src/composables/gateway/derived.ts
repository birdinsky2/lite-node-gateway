import { computed } from "vue";

import { navItems } from "@/constants/navigation";
import type { GatewayManagerState } from "@/composables/gateway/state";
import type { Binding, NodeItem, SystemProxyState } from "@/types/gateway";
import type { TagTone } from "@/types/ui";
import { bindingKey, nodeKey } from "@/utils/gateway";

const defaultSystemProxy: SystemProxyState = {
  enabled: false,
  desired_enabled: false,
  server: "127.0.0.1:7896",
  server_port: 7896,
  bypass: "",
  default_bypass: "",
  helper_ok: false,
  helper: { ok: false },
  selected_subscription_id: null,
  selected_node_id: null,
  selected_label: null,
  selected_resolved: false,
  updated_at: null,
};

export function useGatewayDerived(state: GatewayManagerState) {
  const activeMeta = computed(() => navItems.find((item) => item.key === state.activeView.value) ?? navItems[0]);
  const subscriptions = computed(() => state.stateData.value?.subscriptions ?? []);
  const bindings = computed<Binding[]>(() => state.stateData.value?.bindings ?? []);
  const systemProxy = computed(() => state.stateData.value?.system_proxy ?? defaultSystemProxy);

  const activeSubscription = computed(
    () => subscriptions.value.find((item) => item.id === state.selectedSubscriptionId.value) ?? null,
  );
  const systemProxyActiveSubscription = computed(
    () => subscriptions.value.find((item) => item.id === state.systemProxySubscriptionId.value) ?? null,
  );

  const portRange = computed(() => {
    const min = state.stateData.value?.port_min ?? 7900;
    const max = state.stateData.value?.port_max ?? 7999;
    return `${min}-${max}`;
  });

  const totalPorts = computed(() => {
    const min = state.stateData.value?.port_min ?? 7900;
    const max = state.stateData.value?.port_max ?? 7999;
    return Math.max(1, max - min + 1);
  });

  const freePortCount = computed(() => Math.max(totalPorts.value - bindings.value.length, 0));
  const portUsagePercent = computed(() => Math.min(100, Math.round((bindings.value.length / totalPorts.value) * 100)));
  const totalNodeCount = computed(() =>
    subscriptions.value.reduce((count, item) => count + Number(item.node_count || 0), 0),
  );

  const coreVersion = computed(() => {
    const version = state.stateData.value?.core.body?.version;
    if (typeof version === "string" && version.trim()) return version;
    return state.stateData.value?.core.ok ? "已连接" : "未连接";
  });

  const nodeTypes = computed(() => nodeTypeOptions(state.nodes.value));
  const systemProxyNodeTypes = computed(() => nodeTypeOptions(state.systemProxyNodes.value));

  const filteredNodes = computed(() =>
    filterAndSortNodes(state.nodes.value, state.nodeQuery.value, state.typeFilter.value, state.nodeSort.value, sortableDelay),
  );
  const filteredSystemProxyNodes = computed(() =>
    filterAndSortNodes(
      state.systemProxyNodes.value,
      state.systemProxyQuery.value,
      state.systemProxyTypeFilter.value,
      state.systemProxySort.value,
      sortableDelay,
    ),
  );

  const nodeBindingMap = computed(() => {
    const map = new Map<string, Binding[]>();
    for (const binding of bindings.value) {
      if (binding.mode !== "node" || !binding.subscription_id || !binding.node_id) continue;
      const key = bindingKey(binding.subscription_id, binding.node_id);
      map.set(key, [...(map.get(key) ?? []), binding]);
    }
    return map;
  });

  const boundNodeCount = computed(() => nodeBindingMap.value.size);
  const selectedNodeBindings = computed(() => (state.selectedNode.value ? nodeBindings(state.selectedNode.value) : []));

  const nodeSubtitle = computed(() => {
    if (!state.selectedSubscriptionId.value) return "选择一个订阅查看节点";
    if (state.loadingNodes.value) return "节点加载中";
    return `${filteredNodes.value.length}/${state.nodes.value.length} 个节点`;
  });

  const systemProxySubtitle = computed(() => {
    if (!state.systemProxySubscriptionId.value) return "选择一个订阅来查看可用于系统代理的节点";
    if (state.loadingSystemProxyNodes.value) return "节点加载中";
    return `${filteredSystemProxyNodes.value.length}/${state.systemProxyNodes.value.length} 个节点`;
  });

  const selectedTargetLabel = computed(() => {
    if (state.bindingMode.value === "builtin") return `内置目标：${state.builtinTarget.value}`;
    if (!state.selectedNode.value) return "未选择节点";
    return `${state.selectedNode.value.subscription_name} / ${state.selectedNode.value.name}`;
  });

  const bindingSubtitle = computed(() => {
    const count = bindings.value.length;
    return count ? `${count} 个固定端口，剩余 ${freePortCount.value} 个可用` : "当前没有固定端口";
  });

  const systemProxyStatusLabel = computed(() => {
    if (systemProxy.value.helper.supported === false) return "系统代理后端不可用";
    if (!systemProxy.value.helper_ok) return "Helper 未连接";
    return systemProxy.value.enabled ? "系统代理已打开" : "系统代理已关闭";
  });

  const systemProxyStatusTone = computed<TagTone>(() => {
    if (systemProxy.value.helper.supported === false) return "warning";
    if (!systemProxy.value.helper_ok) return "danger";
    return systemProxy.value.enabled ? "success" : "info";
  });

  const systemProxySelectedLabel = computed(() => {
    if (systemProxy.value.selected_label) return systemProxy.value.selected_label;
    if (state.systemProxySelectedNode.value) {
      return `${state.systemProxySelectedNode.value.subscription_name} / ${state.systemProxySelectedNode.value.name}`;
    }
    return "未选择节点";
  });

  function nodeBindings(node: NodeItem) {
    return nodeBindingMap.value.get(nodeKey(node)) ?? [];
  }

  function nodeIsOpened(node: NodeItem) {
    return nodeBindings(node).length > 0;
  }

  function nodeBindingLabel(node: NodeItem) {
    const ports = nodeBindings(node).map((binding) => binding.port);
    return ports.length ? `已开 ${ports.join(", ")}` : "";
  }

  function nextFreePort() {
    const min = state.stateData.value?.port_min ?? 7900;
    const max = state.stateData.value?.port_max ?? 7999;
    const used = new Set(bindings.value.map((item) => Number(item.port)));
    for (let port = min; port <= max; port += 1) {
      if (!used.has(port)) return port;
    }
    return min;
  }

  function nodeDelay(node: NodeItem) {
    return state.nodeDelayResults.value[nodeKey(node)];
  }

  function nodeDelayTesting(node: NodeItem) {
    return state.testingNodeDelayKeys.value.has(nodeKey(node));
  }

  function sortableDelay(node: NodeItem) {
    const result = nodeDelay(node);
    return result?.ok && typeof result.delay_ms === "number" && result.delay_ms > 0
      ? result.delay_ms
      : Number.POSITIVE_INFINITY;
  }

  function nodeDelayLabel(node: NodeItem) {
    const result = nodeDelay(node);
    if ((state.testingDelays.value || nodeDelayTesting(node)) && !result) return "测速中";
    if (!result) return "未测";
    if (result.ok && typeof result.delay_ms === "number" && result.delay_ms > 0) return `${result.delay_ms} ms`;
    return "超时";
  }

  function systemProxyNodeDelayLabel(node: NodeItem) {
    const result = nodeDelay(node);
    if (state.testingSystemProxyDelays.value && !result) return "测速中";
    if (!result) return "未测";
    if (result.ok && typeof result.delay_ms === "number" && result.delay_ms > 0) return `${result.delay_ms} ms`;
    return "超时";
  }

  function nodeDelayTagType(node: NodeItem): TagTone {
    const result = nodeDelay(node);
    if (!result) return "info";
    if (!result.ok || typeof result.delay_ms !== "number" || result.delay_ms <= 0) return "danger";
    if (result.delay_ms <= 160) return "success";
    if (result.delay_ms <= 700) return "warning";
    return "danger";
  }

  function bindingTagType(binding: Binding): TagTone {
    if (!binding.resolved) return "danger";
    return binding.mode === "node" ? "success" : "info";
  }

  function systemProxyNodeSelected(node: NodeItem) {
    return systemProxy.value.selected_subscription_id === node.subscription_id && systemProxy.value.selected_node_id === node.id;
  }

  return {
    activeMeta,
    subscriptions,
    bindings,
    systemProxy,
    activeSubscription,
    systemProxyActiveSubscription,
    portRange,
    freePortCount,
    portUsagePercent,
    totalNodeCount,
    coreVersion,
    nodeTypes,
    systemProxyNodeTypes,
    filteredNodes,
    filteredSystemProxyNodes,
    boundNodeCount,
    selectedNodeBindings,
    nodeSubtitle,
    systemProxySubtitle,
    selectedTargetLabel,
    bindingSubtitle,
    systemProxyStatusLabel,
    systemProxyStatusTone,
    systemProxySelectedLabel,
    nodeBindings,
    nodeIsOpened,
    nodeBindingLabel,
    nodeDelayLabel,
    nodeDelayTesting,
    systemProxyNodeDelayLabel,
    nodeDelayTagType,
    bindingTagType,
    systemProxyNodeSelected,
    nextFreePort,
  };
}

function nodeTypeOptions(nodes: NodeItem[]) {
  const types = new Set(nodes.map((node) => node.type).filter(Boolean));
  return Array.from(types).sort((a, b) => a.localeCompare(b));
}

function filterAndSortNodes(
  nodes: NodeItem[],
  queryValue: string,
  typeFilter: string,
  sortMode: "default" | "delay-asc" | "delay-desc",
  delayOf: (node: NodeItem) => number,
) {
  const query = queryValue.trim().toLowerCase();
  const filtered = nodes.filter((node) => {
    const typeMatched = typeFilter === "all" || node.type === typeFilter;
    const haystack = `${node.name} ${node.type} ${node.server} ${node.subscription_name}`.toLowerCase();
    return typeMatched && (!query || haystack.includes(query));
  });
  if (sortMode === "default") return filtered;
  return [...filtered].sort((left, right) => {
    const leftDelay = delayOf(left);
    const rightDelay = delayOf(right);
    const leftMissing = !Number.isFinite(leftDelay);
    const rightMissing = !Number.isFinite(rightDelay);
    if (leftMissing && rightMissing) return 0;
    if (leftMissing) return 1;
    if (rightMissing) return -1;
    return sortMode === "delay-asc" ? leftDelay - rightDelay : rightDelay - leftDelay;
  });
}

export type GatewayDerived = ReturnType<typeof useGatewayDerived>;
