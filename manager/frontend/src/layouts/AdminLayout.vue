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
      <DashboardView v-if="manager.activeView.value === 'dashboard'" />
      <SubscriptionsView v-else-if="manager.activeView.value === 'subscriptions'" />
      <NodesView v-else-if="manager.activeView.value === 'nodes'" />
      <SettingsView v-else-if="manager.activeView.value === 'settings'" />
      <PortsView v-else />
    </section>
  </main>
</template>

<script setup lang="ts">
import { useGatewayContext } from "@/composables/useGatewayContext";
import AppSidebar from "@/layouts/components/AppSidebar.vue";
import DashboardView from "@/views/dashboard/DashboardView.vue";
import NodesView from "@/views/nodes/NodesView.vue";
import PortsView from "@/views/ports/PortsView.vue";
import SettingsView from "@/views/settings/SettingsView.vue";
import SubscriptionsView from "@/views/subscriptions/SubscriptionsView.vue";

const manager = useGatewayContext();
</script>
