<template>
  <section class="node-workbench">
    <NodeToolbar />

    <div v-loading="manager.loadingNodes.value" class="node-grid-wrap">
      <el-empty
        v-if="!manager.subscriptions.value.length"
        :image-size="120"
        description="暂无订阅，请先到订阅管理导入"
      />
      <el-empty v-else-if="!manager.selectedSubscriptionId.value" :image-size="120" description="请选择订阅" />
      <el-empty v-else-if="!manager.filteredNodes.value.length" :image-size="120" description="暂无匹配节点" />

      <div v-else class="node-grid">
        <NodeCard
          v-for="node in manager.filteredNodes.value"
          :key="node.id"
          :binding-label="manager.nodeBindingLabel(node)"
          :delay-label="manager.nodeDelayLabel(node)"
          :delay-tag-type="manager.nodeDelayTagType(node)"
          :node="node"
          :opened="manager.nodeIsOpened(node)"
          :selected="node.id === manager.selectedNode.value?.id"
          @keydown="manager.handleNodeCardKeydown"
          @select="manager.selectNode"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useGatewayContext } from "@/composables/useGatewayContext";
import NodeCard from "@/views/ports/components/NodeCard.vue";
import NodeToolbar from "@/views/ports/components/NodeToolbar.vue";

const manager = useGatewayContext();
</script>
