<template>
  <article
    :class="[
      'node-card',
      {
        selected,
        opened,
      },
    ]"
    role="button"
    tabindex="0"
    @click="$emit('select', node)"
    @keydown="$emit('keydown', $event, node)"
  >
    <div class="node-card-head">
      <strong>{{ node.name }}</strong>
      <el-icon><Check v-if="selected" /><Grid v-else /></el-icon>
    </div>

    <div class="node-card-tags">
      <el-tag :type="delayTagType" effect="plain" size="small">
        {{ delayLabel }}
      </el-tag>
      <el-tag size="small">{{ node.type || "unknown" }}</el-tag>
      <el-tag v-if="opened" effect="dark" size="small" type="success">
        {{ bindingLabel }}
      </el-tag>
    </div>

    <p class="node-server">{{ node.server || "-" }}:{{ node.port || "-" }}</p>
    <div class="node-card-foot">
      <span>{{ node.subscription_name }}</span>
      <span>{{ opened ? "已开放" : "可开放" }}</span>
    </div>
  </article>
</template>

<script setup lang="ts">
import { Check, Grid } from "@element-plus/icons-vue";

import type { NodeItem } from "@/types/gateway";
import type { TagTone } from "@/types/ui";

defineProps<{
  bindingLabel: string;
  delayLabel: string;
  delayTagType: TagTone;
  node: NodeItem;
  opened: boolean;
  selected: boolean;
}>();

defineEmits<{
  keydown: [event: KeyboardEvent, node: NodeItem];
  select: [node: NodeItem];
}>();
</script>
