<template>
  <header class="admin-header">
    <section class="page-title">
      <div class="title-icon" aria-hidden="true">
        <el-icon><component :is="activeMeta.icon" /></el-icon>
      </div>
      <div>
        <span class="eyebrow">Console</span>
        <h1>{{ activeMeta.label }}</h1>
        <p>{{ activeMeta.longDesc }}</p>
      </div>
    </section>

    <section class="header-metrics" aria-label="运行概览">
      <article class="mini-metric">
        <el-icon><Ticket /></el-icon>
        <span>订阅</span>
        <strong>{{ subscriptionCount }}</strong>
      </article>
      <article class="mini-metric">
        <el-icon><Operation /></el-icon>
        <span>开放端口</span>
        <strong>{{ bindingCount }}</strong>
      </article>
      <article class="mini-metric">
        <el-icon><DataBoard /></el-icon>
        <span>空闲端口</span>
        <strong>{{ freePortCount }}</strong>
      </article>
      <article class="mini-metric">
        <el-icon><TrendCharts /></el-icon>
        <span>核心</span>
        <strong>{{ coreVersion }}</strong>
      </article>
    </section>

    <section class="header-actions">
      <el-tooltip content="刷新状态">
        <el-button :icon="Refresh" :loading="loadingState" @click="$emit('refresh')">刷新</el-button>
      </el-tooltip>
      <el-tooltip content="重新生成并加载 Mihomo 配置">
        <el-button :icon="Switch" :loading="rebuilding" type="primary" @click="$emit('rebuild')">
          重载配置
        </el-button>
      </el-tooltip>
    </section>
  </header>
</template>

<script setup lang="ts">
import { DataBoard, Operation, Refresh, Switch, Ticket, TrendCharts } from "@element-plus/icons-vue";

import type { NavItem } from "@/types/ui";

defineProps<{
  activeMeta: NavItem;
  bindingCount: number;
  coreVersion: string;
  freePortCount: number;
  loadingState: boolean;
  rebuilding: boolean;
  subscriptionCount: number;
}>();

defineEmits<{
  refresh: [];
  rebuild: [];
}>();
</script>
