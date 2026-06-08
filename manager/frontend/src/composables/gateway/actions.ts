import { ElMessage, ElMessageBox } from "element-plus";

import {
  createSubscription,
  deleteBinding,
  deleteSubscription,
  getNodes,
  getState,
  probePort,
  probeSystemProxy,
  rebuildConfig,
  refreshSubscription,
  saveBinding,
  selectSystemProxyNode,
  testNodeDelays,
  updateSystemProxy,
  updateSystemProxySettings,
} from "@/api/gateway";
import type { GatewayDerived } from "@/composables/gateway/derived";
import type { GatewayManagerState } from "@/composables/gateway/state";
import type { NodeItem } from "@/types/gateway";

export function useGatewayActions(state: GatewayManagerState, derived: GatewayDerived) {
  function syncSystemProxySettingsForm() {
    const systemProxy = state.stateData.value?.system_proxy;
    if (!systemProxy) return;
    state.settingsProxyPort.value = systemProxy.server_port || 7896;
    state.settingsBypassText.value = systemProxy.bypass || systemProxy.default_bypass || "";
  }

  function ensureSelectedSubscription() {
    const list = derived.subscriptions.value;
    const systemProxySubscriptionId = state.stateData.value?.system_proxy.selected_subscription_id;

    if (!state.selectedSubscriptionId.value && list.length) {
      state.selectedSubscriptionId.value = list[0].id;
    }
    if (state.selectedSubscriptionId.value && !list.some((item) => item.id === state.selectedSubscriptionId.value)) {
      state.selectedSubscriptionId.value = list[0]?.id ?? null;
      state.selectedNode.value = null;
      state.nodes.value = [];
    }

    if (!state.systemProxySubscriptionId.value && list.length) {
      state.systemProxySubscriptionId.value =
        list.find((item) => item.id === systemProxySubscriptionId)?.id ?? state.selectedSubscriptionId.value ?? list[0].id;
    }
    if (
      state.systemProxySubscriptionId.value &&
      !list.some((item) => item.id === state.systemProxySubscriptionId.value)
    ) {
      state.systemProxySubscriptionId.value = list[0]?.id ?? null;
      state.systemProxySelectedNode.value = null;
      state.systemProxyNodes.value = [];
    }

    if (!list.length) {
      state.selectedNode.value = null;
      state.nodes.value = [];
      state.systemProxySelectedNode.value = null;
      state.systemProxyNodes.value = [];
    }
  }

  async function loadState(showNotice = false) {
    state.loadingState.value = true;
    try {
      state.stateData.value = await getState();
      ensureSelectedSubscription();
      syncSystemProxySettingsForm();
      state.bindingPort.value = derived.nextFreePort();

      if (state.selectedSubscriptionId.value) {
        await loadNodes(state.selectedSubscriptionId.value);
      } else {
        state.nodes.value = [];
      }

      if (state.systemProxySubscriptionId.value) {
        await loadSystemProxyNodes(state.systemProxySubscriptionId.value);
      } else {
        state.systemProxyNodes.value = [];
      }

      if (showNotice) ElMessage.success("状态已刷新");
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "状态加载失败");
    } finally {
      state.loadingState.value = false;
    }
  }

  async function loadNodes(subscriptionId: string) {
    state.loadingNodes.value = true;
    try {
      const payload = await getNodes(subscriptionId);
      state.nodes.value = payload.nodes ?? [];
      state.selectedNode.value =
        state.nodes.value.find(
          (node) => node.id === state.selectedNode.value?.id && node.subscription_id === state.selectedNode.value?.subscription_id,
        ) ?? null;
      if (state.typeFilter.value !== "all" && !derived.nodeTypes.value.includes(state.typeFilter.value)) {
        state.typeFilter.value = "all";
      }
    } catch (error) {
      state.nodes.value = [];
      ElMessage.error(error instanceof Error ? error.message : "节点加载失败");
    } finally {
      state.loadingNodes.value = false;
    }
  }

  async function loadSystemProxyNodes(subscriptionId: string) {
    state.loadingSystemProxyNodes.value = true;
    try {
      const payload = await getNodes(subscriptionId);
      state.systemProxyNodes.value = payload.nodes ?? [];
      state.systemProxySelectedNode.value =
        state.systemProxyNodes.value.find((node) => derived.systemProxyNodeSelected(node)) ??
        state.systemProxyNodes.value.find(
          (node) =>
            node.id === state.systemProxySelectedNode.value?.id &&
            node.subscription_id === state.systemProxySelectedNode.value?.subscription_id,
        ) ??
        null;
      if (
        state.systemProxyTypeFilter.value !== "all" &&
        !derived.systemProxyNodeTypes.value.includes(state.systemProxyTypeFilter.value)
      ) {
        state.systemProxyTypeFilter.value = "all";
      }
    } catch (error) {
      state.systemProxyNodes.value = [];
      ElMessage.error(error instanceof Error ? error.message : "系统代理节点加载失败");
    } finally {
      state.loadingSystemProxyNodes.value = false;
    }
  }

  async function selectSubscription(subscriptionId: string) {
    state.selectedSubscriptionId.value = subscriptionId;
    state.selectedNode.value = null;
    state.nodeQuery.value = "";
    state.typeFilter.value = "all";
    state.nodeSort.value = "default";
    await loadNodes(subscriptionId);
  }

  async function selectSystemProxySubscription(subscriptionId: string) {
    state.systemProxySubscriptionId.value = subscriptionId;
    state.systemProxySelectedNode.value = null;
    state.systemProxyQuery.value = "";
    state.systemProxyTypeFilter.value = "all";
    state.systemProxySort.value = "default";
    await loadSystemProxyNodes(subscriptionId);
  }

  function handleSubscriptionChange(value: string | number | boolean | undefined) {
    if (typeof value === "string") {
      void selectSubscription(value);
    }
  }

  function handleSystemProxySubscriptionChange(value: string | number | boolean | undefined) {
    if (typeof value === "string") {
      void selectSystemProxySubscription(value);
    }
  }

  async function openSubscriptionNodes(subscriptionId: string) {
    state.activeView.value = "nodes";
    await selectSubscription(subscriptionId);
  }

  function selectNode(node: NodeItem) {
    state.selectedNode.value = node;
    state.bindingMode.value = "node";
    state.bindingPort.value = derived.nextFreePort();
  }

  function handleNodeCardKeydown(event: KeyboardEvent, node: NodeItem) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    selectNode(node);
  }

  async function selectSystemProxyNodeAction(node: NodeItem) {
    state.savingSystemProxy.value = true;
    try {
      await selectSystemProxyNode({
        subscription_id: node.subscription_id,
        node_id: node.id,
      });
      state.systemProxySelectedNode.value = node;
      ElMessage.success("系统代理节点已切换");
      await loadState();
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "系统代理节点切换失败");
    } finally {
      state.savingSystemProxy.value = false;
    }
  }

  function handleSystemProxyNodeKeydown(event: KeyboardEvent, node: NodeItem) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    void selectSystemProxyNodeAction(node);
  }

  async function handleToggleSystemProxy(enabled: boolean) {
    state.savingSystemProxy.value = true;
    try {
      const payload = await updateSystemProxy({ enabled });
      if (state.stateData.value) {
        state.stateData.value.system_proxy = payload.system_proxy;
      }
      ElMessage.success(enabled ? "系统代理已打开" : "系统代理已关闭");
      await loadState();
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "系统代理开关失败");
      await loadState();
    } finally {
      state.savingSystemProxy.value = false;
    }
  }

  async function handleSaveSystemProxySettings() {
    const port = Number(state.settingsProxyPort.value);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      ElMessage.warning("系统代理端口必须是 1-65535 之间的数字");
      return;
    }

    state.savingSystemProxySettings.value = true;
    try {
      const payload = await updateSystemProxySettings({
        server_port: port,
        bypass: state.settingsBypassText.value,
      });
      if (state.stateData.value) {
        state.stateData.value.system_proxy = payload.system_proxy;
      }
      syncSystemProxySettingsForm();
      ElMessage.success("系统代理设置已保存");
      await loadState();
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "系统代理设置保存失败");
      await loadState();
    } finally {
      state.savingSystemProxySettings.value = false;
    }
  }

  function handleResetSystemProxyBypass() {
    state.settingsBypassText.value = derived.systemProxy.value.default_bypass || "";
  }

  async function handleCreateSubscription() {
    const url = state.subscriptionForm.url.trim();
    if (!url) {
      ElMessage.warning("请填写订阅地址");
      return false;
    }
    state.creatingSubscription.value = true;
    try {
      const payload = await createSubscription({
        name: state.subscriptionForm.name.trim(),
        url,
      });
      state.subscriptionForm.name = "";
      state.subscriptionForm.url = "";
      state.selectedSubscriptionId.value = payload.subscription.id;
      state.systemProxySubscriptionId.value = payload.subscription.id;
      state.activeView.value = "nodes";
      ElMessage.success("订阅已导入");
      await loadState();
      return true;
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "订阅导入失败");
      return false;
    } finally {
      state.creatingSubscription.value = false;
    }
  }

  async function handleRefreshSubscription(subscriptionId: string) {
    state.refreshingId.value = subscriptionId;
    try {
      await refreshSubscription(subscriptionId);
      ElMessage.success("订阅已刷新");
      await loadState();
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "订阅刷新失败");
    } finally {
      state.refreshingId.value = null;
    }
  }

  async function handleDeleteSubscription(subscriptionId: string) {
    try {
      await ElMessageBox.confirm("删除订阅会同时移除它关联的端口映射。", "删除订阅", {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      });
      await deleteSubscription(subscriptionId);
      ElMessage.success("订阅已删除");
      await loadState();
    } catch (error) {
      if (error !== "cancel" && error !== "close") {
        ElMessage.error(error instanceof Error ? error.message : "订阅删除失败");
      }
    }
  }

  async function handleSaveBinding() {
    if (state.bindingMode.value === "node" && !state.selectedNode.value) {
      ElMessage.warning("请先选择节点");
      return false;
    }
    state.savingBinding.value = true;
    try {
      await saveBinding(
        state.bindingMode.value === "builtin"
          ? { port: state.bindingPort.value, target: state.builtinTarget.value }
          : {
              port: state.bindingPort.value,
              subscription_id: state.selectedNode.value?.subscription_id,
              node_id: state.selectedNode.value?.id,
            },
      );
      ElMessage.success("端口已保存");
      await loadState();
      return true;
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "端口保存失败");
      return false;
    } finally {
      state.savingBinding.value = false;
    }
  }

  async function handleDeleteBinding(port: number) {
    try {
      await ElMessageBox.confirm(`确认删除 ${port} 端口映射？`, "删除端口", {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      });
      await deleteBinding(port);
      ElMessage.success("端口已删除");
      await loadState();
    } catch (error) {
      if (error !== "cancel" && error !== "close") {
        ElMessage.error(error instanceof Error ? error.message : "端口删除失败");
      }
    }
  }

  async function handleRebuild() {
    state.rebuilding.value = true;
    try {
      await rebuildConfig();
      ElMessage.success("配置已重载");
      await loadState();
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "配置重载失败");
    } finally {
      state.rebuilding.value = false;
    }
  }

  async function handleTestAllDelays() {
    if (!state.selectedSubscriptionId.value) {
      ElMessage.warning("请先选择订阅");
      return;
    }
    if (!state.nodes.value.length) {
      ElMessage.warning("当前订阅没有可测速节点");
      return;
    }
    state.testingDelays.value = true;
    try {
      const payload = await testNodeDelays(state.selectedSubscriptionId.value);
      state.nodeDelayResults.value = {
        ...state.nodeDelayResults.value,
        ...Object.fromEntries(payload.results.map((item) => [item.node_id, item])),
      };
      state.nodeSort.value = "delay-asc";
      ElMessage.success(`测速完成：${payload.ok_count}/${payload.count} 个节点可用`);
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "节点测速失败");
    } finally {
      state.testingDelays.value = false;
    }
  }

  async function handleTestSystemProxyDelays() {
    if (!state.systemProxySubscriptionId.value) {
      ElMessage.warning("请先选择订阅");
      return;
    }
    if (!state.systemProxyNodes.value.length) {
      ElMessage.warning("当前订阅没有可测速节点");
      return;
    }
    state.testingSystemProxyDelays.value = true;
    try {
      const payload = await testNodeDelays(state.systemProxySubscriptionId.value);
      state.nodeDelayResults.value = {
        ...state.nodeDelayResults.value,
        ...Object.fromEntries(payload.results.map((item) => [item.node_id, item])),
      };
      state.systemProxySort.value = "delay-asc";
      ElMessage.success(`测速完成：${payload.ok_count}/${payload.count} 个节点可用`);
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "节点测速失败");
    } finally {
      state.testingSystemProxyDelays.value = false;
    }
  }

  async function handleProbe(port: number) {
    state.probingPort.value = port;
    try {
      const result = await probePort(port);
      ElMessage.success(`测试成功：HTTP ${result.status ?? "-"}，${result.elapsed_ms} ms`);
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "端口测试失败");
    } finally {
      state.probingPort.value = null;
    }
  }

  async function handleProbeSystemProxy() {
    state.probingSystemProxy.value = true;
    state.systemProxyProbeResult.value = null;
    try {
      const result = await probeSystemProxy();
      state.systemProxyProbeResult.value = result;
      ElMessage.success(`测试成功：HTTP ${result.status ?? "-"}，${result.elapsed_ms} ms`);
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "系统代理测试失败");
    } finally {
      state.probingSystemProxy.value = false;
    }
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      ElMessage.success("已复制");
    } catch {
      ElMessage.warning("复制失败");
    }
  }

  return {
    loadState,
    loadSystemProxyNodes,
    handleSubscriptionChange,
    handleSystemProxySubscriptionChange,
    openSubscriptionNodes,
    selectNode,
    selectSystemProxyNodeAction,
    handleNodeCardKeydown,
    handleSystemProxyNodeKeydown,
    handleToggleSystemProxy,
    handleSaveSystemProxySettings,
    handleResetSystemProxyBypass,
    handleCreateSubscription,
    handleRefreshSubscription,
    handleDeleteSubscription,
    handleSaveBinding,
    handleDeleteBinding,
    handleRebuild,
    handleTestAllDelays,
    handleTestSystemProxyDelays,
    handleProbe,
    handleProbeSystemProxy,
    copyText,
  };
}
