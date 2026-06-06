<template>
  <article
    :class="['system-node-card', { selected, disabled }]"
    role="button"
    tabindex="0"
    @click="handleSelect"
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
      <el-tag v-if="selected" effect="dark" size="small" type="success">
        当前系统节点
      </el-tag>
    </div>

    <p class="node-server">{{ node.server || "-" }}:{{ node.port || "-" }}</p>
    <div class="node-card-foot">
      <span>{{ node.subscription_name }}</span>
      <span>{{ selected ? "已选中" : "设为出口" }}</span>
    </div>
  </article>
</template>

<script setup lang="ts">
import { Check, Grid } from "@element-plus/icons-vue";

import type { NodeItem } from "@/types/gateway";
import type { TagTone } from "@/types/ui";

const props = defineProps<{
  delayLabel: string;
  delayTagType: TagTone;
  disabled: boolean;
  node: NodeItem;
  selected: boolean;
}>();

const emit = defineEmits<{
  keydown: [event: KeyboardEvent, node: NodeItem];
  select: [node: NodeItem];
}>();

function handleSelect() {
  if (props.disabled) return;
  emit("select", props.node);
}
</script>
