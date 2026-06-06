<template>
  <section class="content-page system-proxy-page">
    <section class="system-proxy-workspace">
      <SystemProxyControlPanel />
      <SystemProxyNodePicker />
    </section>
  </section>
</template>

<script setup lang="ts">
import SystemProxyControlPanel from "@/views/system-proxy/components/SystemProxyControlPanel.vue";
import SystemProxyNodePicker from "@/views/system-proxy/components/SystemProxyNodePicker.vue";
</script>
