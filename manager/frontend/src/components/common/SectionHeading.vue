<template>
  <div :class="['section-heading', { 'with-tools': withTools, compact }]">
    <div>
      <span class="eyebrow">{{ eyebrow }}</span>
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </div>
    <slot name="aside">
      <el-icon v-if="icon">
        <component :is="icon" />
      </el-icon>
    </slot>
  </div>
</template>

<script setup lang="ts">
import type { Component } from "vue";

defineProps<{
  eyebrow: string;
  title: string;
  description?: string;
  icon?: Component;
  withTools?: boolean;
  compact?: boolean;
}>();
</script>
