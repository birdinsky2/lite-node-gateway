<template>
  <aside class="system-proxy-panel">
    <SectionHeading
      eyebrow="System"
      title="系统代理"
      :description="manager.systemProxySelectedLabel.value"
      :icon="SwitchButton"
    />

    <section class="system-proxy-switch">
      <div>
        <el-tag :type="manager.systemProxyStatusTone.value" effect="dark">
          {{ manager.systemProxyStatusLabel.value }}
        </el-tag>
        <strong>{{ manager.systemProxy.value.enabled ? "ON" : "OFF" }}</strong>
      </div>
      <el-switch
        :disabled="!manager.systemProxy.value.helper_ok || manager.savingSystemProxy.value"
        :loading="manager.savingSystemProxy.value"
        :model-value="manager.systemProxy.value.enabled"
        active-text="打开"
        inactive-text="关闭"
        inline-prompt
        size="large"
        @change="handleSwitchChange"
      />
    </section>

    <dl class="system-proxy-facts">
      <div>
        <dt>本机代理</dt>
        <dd>{{ manager.systemProxy.value.server }}</dd>
      </div>
      <div>
        <dt>Helper</dt>
        <dd>{{ manager.systemProxy.value.helper_ok ? "已连接" : helperError }}</dd>
      </div>
      <div>
        <dt>当前节点</dt>
        <dd>{{ manager.systemProxySelectedLabel.value }}</dd>
      </div>
      <div>
        <dt>更新时间</dt>
        <dd>{{ formatDate(manager.systemProxy.value.updated_at) }}</dd>
      </div>
    </dl>

    <div class="system-proxy-actions">
      <el-button
        :disabled="!manager.systemProxy.value.helper_ok || !manager.systemProxy.value.selected_resolved"
        :icon="Promotion"
        :loading="manager.probingSystemProxy.value"
        type="primary"
        @click="manager.handleProbeSystemProxy"
      >
        测试出口
      </el-button>
      <el-button :icon="Refresh" :loading="manager.loadingState.value" @click="manager.loadState(true)">
        刷新状态
      </el-button>
    </div>

    <section v-if="manager.systemProxyProbeResult.value" class="system-proxy-probe">
      <span>最近测试</span>
      <strong>
        HTTP {{ manager.systemProxyProbeResult.value.status ?? "-" }} ·
        {{ manager.systemProxyProbeResult.value.elapsed_ms }} ms
      </strong>
      <p>{{ manager.systemProxyProbeResult.value.body || manager.systemProxyProbeResult.value.error || "-" }}</p>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Promotion, Refresh, SwitchButton } from "@element-plus/icons-vue";

import SectionHeading from "@/components/common/SectionHeading.vue";
import { useGatewayContext } from "@/composables/useGatewayContext";
import { formatDate } from "@/utils/date";

const manager = useGatewayContext();

const helperError = computed(() => manager.systemProxy.value.helper.error || "未连接");

function handleSwitchChange(value: string | number | boolean) {
  void manager.handleToggleSystemProxy(Boolean(value));
}
</script>
