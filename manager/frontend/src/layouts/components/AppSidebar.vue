<template>
  <aside class="admin-sidebar">
    <section class="sidebar-brand" aria-label="Lite Node Gateway">
      <div class="brand-mark" aria-hidden="true">
        <Connection />
      </div>
      <div class="brand-copy">
        <strong>Lite Node Gateway</strong>
        <span>Proxy Manager</span>
      </div>
    </section>

    <nav class="sidebar-nav" aria-label="后台菜单">
      <button
        v-for="item in navItems"
        :key="item.key"
        :class="['nav-entry', { active: activeView === item.key }]"
        type="button"
        @click="$emit('update:activeView', item.key)"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span class="nav-copy">
          <strong>{{ item.label }}</strong>
        </span>
      </button>
    </nav>

    <section class="sidebar-status" aria-label="版本与运行状态">
      <div :class="['status-orb', coreOnline ? 'online' : 'offline']" aria-hidden="true"></div>
      <div>
        <strong>{{ coreOnline ? "Mihomo 在线" : "Mihomo 离线" }}</strong>
        <span>v1.0.0-beta · {{ portRange }}</span>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { Connection } from "@element-plus/icons-vue";

import { navItems } from "@/constants/navigation";
import type { ViewKey } from "@/router/views";

defineProps<{
  activeView: ViewKey;
  bindingCount: number;
  coreOnline: boolean;
  portRange: string;
  systemProxyEnabled: boolean;
  systemProxyPort: number;
  systemProxyReady: boolean;
  subscriptionCount: number;
}>();

defineEmits<{
  "update:activeView": [value: ViewKey];
}>();
</script>
