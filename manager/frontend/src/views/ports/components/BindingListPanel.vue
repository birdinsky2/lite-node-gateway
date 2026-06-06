<template>
  <section class="binding-panel">
    <SectionHeading eyebrow="Ports" title="已开放端口" :description="manager.bindingSubtitle.value" compact>
      <template #aside>
        <el-tag type="info">{{ manager.bindings.value.length }}</el-tag>
      </template>
    </SectionHeading>

    <div class="port-usage" aria-label="端口使用率">
      <span :style="{ width: `${manager.portUsagePercent.value}%` }"></span>
    </div>

    <el-empty v-if="!manager.bindings.value.length" :image-size="92" description="暂无端口映射" />

    <div v-else class="binding-list">
      <article
        v-for="binding in manager.bindings.value"
        :key="binding.port"
        :class="['binding-item', { muted: !binding.resolved }]"
      >
        <div class="binding-main">
          <strong>{{ binding.port }}</strong>
          <div>
            <span>{{ binding.label || binding.target || "-" }}</span>
            <small>{{ binding.mode === "node" ? "节点映射" : "内置目标" }}</small>
          </div>
          <el-tag :type="manager.bindingTagType(binding)" size="small">
            {{ binding.resolved ? binding.mode : "失效" }}
          </el-tag>
        </div>

        <div class="proxy-line">
          <span>{{ binding.host_proxy }}</span>
          <el-tooltip content="复制本机代理地址">
            <el-button :icon="CopyDocument" circle size="small" @click="manager.copyText(binding.host_proxy)" />
          </el-tooltip>
        </div>
        <div class="proxy-line muted">
          <span>{{ binding.container_proxy }}</span>
          <el-tooltip content="复制容器代理地址">
            <el-button :icon="CopyDocument" circle size="small" @click="manager.copyText(binding.container_proxy)" />
          </el-tooltip>
        </div>

        <div class="binding-actions">
          <el-button :icon="Promotion" :loading="manager.probingPort.value === binding.port" @click="manager.handleProbe(binding.port)">
            测试
          </el-button>
          <el-button :icon="Delete" type="danger" @click="manager.handleDeleteBinding(binding.port)">删除</el-button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { CopyDocument, Delete, Promotion } from "@element-plus/icons-vue";

import { useGatewayContext } from "@/composables/useGatewayContext";
import SectionHeading from "@/components/common/SectionHeading.vue";

const manager = useGatewayContext();
</script>
