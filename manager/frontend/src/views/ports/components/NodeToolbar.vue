<template>
  <div class="node-toolbar">
    <SectionHeading eyebrow="Nodes" title="代理节点" :description="manager.nodeSubtitle.value">
      <template #aside>
        <span></span>
      </template>
    </SectionHeading>

    <div class="toolbar-controls">
      <el-select
        v-model="manager.selectedSubscriptionId.value"
        filterable
        placeholder="选择订阅"
        @change="manager.handleSubscriptionChange"
      >
        <el-option
          v-for="subscription in manager.subscriptions.value"
          :key="subscription.id"
          :label="`${subscription.name} (${subscription.node_count})`"
          :value="subscription.id"
        />
      </el-select>
      <el-input
        v-model="manager.nodeQuery.value"
        :prefix-icon="Search"
        clearable
        placeholder="搜索地区、协议、域名"
      />
      <el-select v-model="manager.typeFilter.value" placeholder="协议">
        <el-option label="全部协议" value="all" />
        <el-option v-for="type in manager.nodeTypes.value" :key="type" :label="type" :value="type" />
      </el-select>
      <el-select v-model="manager.nodeSort.value" placeholder="排序">
        <el-option label="默认排序" value="default" />
        <el-option label="时延升序" value="delay-asc" />
        <el-option label="时延降序" value="delay-desc" />
      </el-select>
      <el-button
        :disabled="!manager.selectedSubscriptionId.value || !manager.nodes.value.length || manager.loadingNodes.value"
        :icon="Promotion"
        :loading="manager.testingDelays.value"
        type="primary"
        @click="manager.handleTestAllDelays"
      >
        一键测速
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Promotion, Search } from "@element-plus/icons-vue";

import { useGatewayContext } from "@/composables/useGatewayContext";
import SectionHeading from "@/components/common/SectionHeading.vue";

const manager = useGatewayContext();
</script>
