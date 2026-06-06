<template>
  <article :class="['subscription-card', { active }]">
    <div class="card-topline">
      <div class="subscription-title">
        <strong>{{ subscription.name }}</strong>
        <span>{{ subscription.url_masked }}</span>
      </div>
      <el-tag :type="subscription.last_error ? 'danger' : 'success'" effect="light">
        {{ subscription.last_error ? "异常" : "正常" }}
      </el-tag>
    </div>

    <dl class="card-facts">
      <div>
        <dt>节点数</dt>
        <dd>{{ subscription.node_count }}</dd>
      </div>
      <div>
        <dt>更新时间</dt>
        <dd>{{ formatDate(subscription.updated_at) }}</dd>
      </div>
      <div>
        <dt>状态</dt>
        <dd>{{ subscription.enabled ? "启用" : "停用" }}</dd>
      </div>
    </dl>

    <p v-if="subscription.last_error" class="inline-error">
      <WarningFilled />
      <span>{{ subscription.last_error }}</span>
    </p>

    <div class="card-actions">
      <el-button :icon="Refresh" :loading="refreshing" @click="$emit('refresh', subscription.id)">刷新</el-button>
      <el-button :icon="Monitor" type="primary" @click="$emit('openNodes', subscription.id)">查看节点</el-button>
      <el-button :icon="Delete" type="danger" @click="$emit('delete', subscription.id)">删除</el-button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { Delete, Monitor, Refresh, WarningFilled } from "@element-plus/icons-vue";

import type { Subscription } from "@/types/gateway";
import { formatDate } from "@/utils/date";

defineProps<{
  active: boolean;
  refreshing: boolean;
  subscription: Subscription;
}>();

defineEmits<{
  delete: [subscriptionId: string];
  openNodes: [subscriptionId: string];
  refresh: [subscriptionId: string];
}>();
</script>
