<template>
  <section class="content-page subscriptions-page">
    <section class="overview-strip" aria-label="订阅状态">
      <article class="overview-card accent-a">
        <span>订阅总数</span>
        <strong>{{ manager.subscriptions.value.length }}</strong>
        <small>{{ manager.totalNodeCount.value }} 个节点已导入</small>
      </article>
      <article class="overview-card accent-b">
        <span>当前订阅</span>
        <strong>{{ manager.activeSubscription.value?.name || "未选择" }}</strong>
        <small>
          {{
            manager.activeSubscription.value
              ? `${manager.activeSubscription.value.node_count} 个节点`
              : "导入后自动选择"
          }}
        </small>
      </article>
      <article class="overview-card accent-c">
        <span>绑定节点</span>
        <strong>{{ manager.boundNodeCount.value }}</strong>
        <small>{{ manager.bindings.value.length }} 个端口映射</small>
      </article>
    </section>

    <section class="subscription-layout">
      <SubscriptionImportPanel />

      <section class="subscription-main">
        <SectionHeading
          eyebrow="Catalog"
          title="订阅列表"
          description="所有订阅以卡片形式管理，可刷新、删除或切换到节点视图。"
          with-tools
        >
          <template #aside>
            <el-tag size="large">{{ manager.subscriptions.value.length }} 个订阅</el-tag>
          </template>
        </SectionHeading>

        <el-empty
          v-if="!manager.subscriptions.value.length"
          :image-size="120"
          description="暂无订阅，先导入一个订阅地址"
        />

        <div v-else class="subscription-card-grid">
          <SubscriptionCard
            v-for="subscription in manager.subscriptions.value"
            :key="subscription.id"
            :active="subscription.id === manager.selectedSubscriptionId.value"
            :refreshing="manager.refreshingId.value === subscription.id"
            :subscription="subscription"
            @delete="manager.handleDeleteSubscription"
            @open-nodes="manager.openSubscriptionNodes"
            @refresh="manager.handleRefreshSubscription"
          />
        </div>
      </section>
    </section>
  </section>
</template>

<script setup lang="ts">
import { useGatewayContext } from "@/composables/useGatewayContext";
import SectionHeading from "@/components/common/SectionHeading.vue";
import SubscriptionCard from "@/views/subscriptions/components/SubscriptionCard.vue";
import SubscriptionImportPanel from "@/views/subscriptions/components/SubscriptionImportPanel.vue";

const manager = useGatewayContext();
</script>
