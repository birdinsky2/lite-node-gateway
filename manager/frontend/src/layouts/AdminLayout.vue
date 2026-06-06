<template>
  <main class="admin-shell">
    <AppSidebar
      v-model:active-view="manager.activeView.value"
      :binding-count="manager.bindings.value.length"
      :core-online="Boolean(manager.stateData.value?.core.ok)"
      :port-range="manager.portRange.value"
      :system-proxy-enabled="manager.systemProxy.value.enabled"
      :system-proxy-port="manager.systemProxy.value.server_port"
      :system-proxy-ready="manager.systemProxy.value.helper_ok"
      :subscription-count="manager.subscriptions.value.length"
    />

    <section class="admin-main">
      <AppHeader
        :active-meta="manager.activeMeta.value"
        :binding-count="manager.bindings.value.length"
        :core-version="manager.coreVersion.value"
        :free-port-count="manager.freePortCount.value"
        :loading-state="manager.loadingState.value"
        :rebuilding="manager.rebuilding.value"
        :subscription-count="manager.subscriptions.value.length"
        @refresh="manager.loadState(true)"
        @rebuild="manager.handleRebuild"
      />

      <SubscriptionsView v-if="manager.activeView.value === 'subscriptions'" />
      <SystemProxyView v-else-if="manager.activeView.value === 'system-proxy'" />
      <SettingsView v-else-if="manager.activeView.value === 'settings'" />
      <PortsView v-else />
    </section>
  </main>
</template>

<script setup lang="ts">
import { useGatewayContext } from "@/composables/useGatewayContext";
import AppHeader from "@/layouts/components/AppHeader.vue";
import AppSidebar from "@/layouts/components/AppSidebar.vue";
import PortsView from "@/views/ports/PortsView.vue";
import SettingsView from "@/views/settings/SettingsView.vue";
import SubscriptionsView from "@/views/subscriptions/SubscriptionsView.vue";
import SystemProxyView from "@/views/system-proxy/SystemProxyView.vue";

const manager = useGatewayContext();
</script>
