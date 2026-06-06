<template>
  <section class="system-proxy-node-picker">
    <div class="node-toolbar system-node-toolbar">
      <SectionHeading eyebrow="Nodes" title="选择节点" :description="manager.systemProxySubtitle.value">
        <template #aside>
          <el-tag :type="manager.systemProxy.value.selected_resolved ? 'success' : 'info'" effect="plain">
            {{ manager.systemProxySelectedLabel.value }}
          </el-tag>
        </template>
      </SectionHeading>

      <div class="toolbar-controls system-toolbar-controls">
        <el-select
          v-model="manager.systemProxySubscriptionId.value"
          filterable
          placeholder="选择订阅"
          @change="manager.handleSystemProxySubscriptionChange"
        >
          <el-option
            v-for="subscription in manager.subscriptions.value"
            :key="subscription.id"
            :label="`${subscription.name} (${subscription.node_count})`"
            :value="subscription.id"
          />
        </el-select>
        <el-input
          v-model="manager.systemProxyQuery.value"
          :prefix-icon="Search"
          clearable
          placeholder="搜索地区、协议、域名"
        />
        <el-select v-model="manager.systemProxyTypeFilter.value" placeholder="协议">
          <el-option label="全部协议" value="all" />
          <el-option v-for="type in manager.systemProxyNodeTypes.value" :key="type" :label="type" :value="type" />
        </el-select>
        <el-select v-model="manager.systemProxySort.value" placeholder="排序">
          <el-option label="默认排序" value="default" />
          <el-option label="时延升序" value="delay-asc" />
          <el-option label="时延降序" value="delay-desc" />
        </el-select>
        <el-button
          :disabled="
            !manager.systemProxySubscriptionId.value ||
            !manager.systemProxyNodes.value.length ||
            manager.loadingSystemProxyNodes.value
          "
          :icon="Promotion"
          :loading="manager.testingSystemProxyDelays.value"
          type="primary"
          @click="manager.handleTestSystemProxyDelays"
        >
          一键测速
        </el-button>
      </div>
    </div>

    <div v-loading="manager.loadingSystemProxyNodes.value" class="node-grid-wrap system-node-grid-wrap">
      <el-empty
        v-if="!manager.subscriptions.value.length"
        :image-size="120"
        description="暂无订阅，请先到订阅管理导入"
      />
      <el-empty
        v-else-if="!manager.systemProxySubscriptionId.value"
        :image-size="120"
        description="请选择订阅"
      />
      <el-empty
        v-else-if="!manager.filteredSystemProxyNodes.value.length"
        :image-size="120"
        description="暂无匹配节点"
      />

      <div v-else class="node-grid system-node-grid">
        <SystemProxyNodeCard
          v-for="node in manager.filteredSystemProxyNodes.value"
          :key="`${node.subscription_id}:${node.id}`"
          :delay-label="manager.systemProxyNodeDelayLabel(node)"
          :delay-tag-type="manager.nodeDelayTagType(node)"
          :disabled="manager.savingSystemProxy.value"
          :node="node"
          :selected="manager.systemProxyNodeSelected(node)"
          @keydown="manager.handleSystemProxyNodeKeydown"
          @select="manager.selectSystemProxyNodeAction"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Promotion, Search } from "@element-plus/icons-vue";

import SectionHeading from "@/components/common/SectionHeading.vue";
import { useGatewayContext } from "@/composables/useGatewayContext";
import SystemProxyNodeCard from "@/views/system-proxy/components/SystemProxyNodeCard.vue";

const manager = useGatewayContext();
</script>
