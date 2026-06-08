<template>
  <section class="prototype-page nodes-page">
    <header class="prototype-page-header">
      <div>
        <h1>节点浏览</h1>
        <p>浏览和管理所有代理节点</p>
      </div>
    </header>

    <section class="prototype-toolbar" aria-label="节点筛选">
      <el-select
        v-model="manager.selectedSubscriptionId.value"
        filterable
        placeholder="所有订阅"
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
        placeholder="搜索节点名称或地址..."
      />

      <el-select v-model="manager.typeFilter.value" placeholder="所有类型">
        <el-option label="所有类型" value="all" />
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
    </section>

    <section v-loading="manager.loadingNodes.value" class="prototype-card table-card">
      <el-empty
        v-if="!manager.subscriptions.value.length"
        :image-size="120"
        description="暂无订阅，请先到订阅管理导入"
      />
      <el-empty v-else-if="!manager.filteredNodes.value.length" :image-size="120" description="没有找到符合条件的节点" />

      <div v-else class="node-table" role="table" aria-label="节点列表">
        <div class="node-table-row node-table-head" role="row">
          <div role="columnheader">节点名称</div>
          <div role="columnheader">类型</div>
          <div role="columnheader">地址</div>
          <div role="columnheader">延迟</div>
          <div role="columnheader">状态</div>
          <div role="columnheader">操作</div>
        </div>

        <article
          v-for="node in manager.filteredNodes.value"
          :key="`${node.subscription_id}:${node.id}`"
          :class="['node-table-row', { selected: nodeSelected(node) }]"
          role="row"
        >
          <div class="node-name-cell" role="cell">
            <strong>{{ node.name }}</strong>
            <small>{{ node.subscription_name }}</small>
          </div>
          <div role="cell">
            <el-tag effect="plain" round>{{ node.type || "unknown" }}</el-tag>
          </div>
          <div class="mono-cell" role="cell">{{ node.server || "-" }}:{{ node.port || "-" }}</div>
          <div role="cell">
            <el-tag :type="manager.nodeDelayTagType(node)" effect="light">
              {{ manager.nodeDelayLabel(node) }}
            </el-tag>
          </div>
          <div role="cell">
            <span v-if="manager.nodeIsOpened(node)" class="binding-state">
              <el-icon><Link /></el-icon>
              {{ manager.nodeBindingLabel(node) }}
            </span>
            <span v-else class="muted-text">未绑定</span>
          </div>
          <div class="node-actions" role="cell">
            <el-button :icon="Promotion" :loading="manager.testingDelays.value" size="small" @click="manager.handleTestAllDelays">
              测速
            </el-button>
            <el-button :icon="Link" size="small" type="primary" plain @click="bindNode(node)">
              绑定
            </el-button>
            <el-button
              :icon="Lock"
              :loading="manager.savingSystemProxy.value && manager.systemProxyNodeSelected(node)"
              :type="manager.systemProxyNodeSelected(node) ? 'success' : 'default'"
              size="small"
              @click="manager.selectSystemProxyNodeAction(node)"
            >
              {{ manager.systemProxyNodeSelected(node) ? "系统代理" : "设为代理" }}
            </el-button>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { Link, Lock, Promotion, Search } from "@element-plus/icons-vue";

import { useGatewayContext } from "@/composables/useGatewayContext";
import type { NodeItem } from "@/types/gateway";

const manager = useGatewayContext();

function nodeSelected(node: NodeItem) {
  return (
    manager.selectedNode.value?.id === node.id &&
    manager.selectedNode.value?.subscription_id === node.subscription_id
  );
}

function bindNode(node: NodeItem) {
  manager.selectNode(node);
  manager.activeView.value = "ports";
}
</script>
