<template>
  <section class="prototype-page ports-page">
    <header class="prototype-page-header">
      <div>
        <h1>端口绑定</h1>
        <p>将选定的节点暴露到本地端口 ({{ manager.portRange.value }})</p>
      </div>
      <el-button :icon="Plus" type="primary" @click="openBindingDialog">
        新增绑定
      </el-button>
    </header>

    <section class="info-banner">
      <el-icon><WarningFilled /></el-icon>
      <div>
        <strong>热重载已激活</strong>
        <p>保存修改后，将自动生成并重载 Mihomo 核心配置，无需手动重启。</p>
      </div>
    </section>

    <section class="prototype-card table-card">
      <el-table :data="manager.bindings.value" empty-text="暂无绑定的端口" stripe>
        <el-table-column label="本地端口" width="130">
          <template #default="{ row }: { row: Binding }">
            <code class="port-chip">{{ row.port }}</code>
          </template>
        </el-table-column>
        <el-table-column label="目标 / 节点" min-width="240">
          <template #default="{ row }: { row: Binding }">
            <span v-if="row.mode === 'node'" class="target-cell">
              <el-icon><Switch /></el-icon>
              {{ row.label || row.target || "-" }}
            </span>
            <el-tag v-else :type="bindingBuiltinType(row.target)" effect="light">
              {{ row.target || row.label || "内置目标" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="160">
          <template #default="{ row }: { row: Binding }">
            <span class="muted-text">{{ row.mode === "node" ? "订阅节点" : "系统" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="代理地址" min-width="260">
          <template #default="{ row }: { row: Binding }">
            <code class="table-code selectable" @click="manager.copyText(row.host_proxy)">
              {{ row.host_proxy }}
            </code>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }: { row: Binding }">
            <el-tag :type="manager.bindingTagType(row)" effect="light">
              {{ row.resolved ? "可用" : "失效" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column align="right" label="操作" width="150">
          <template #default="{ row }: { row: Binding }">
            <div class="table-actions">
              <el-tooltip content="测试">
                <el-button
                  :icon="Promotion"
                  :loading="manager.probingPort.value === row.port"
                  aria-label="测试端口"
                  circle
                  @click="manager.handleProbe(row.port)"
                />
              </el-tooltip>
              <el-tooltip content="删除">
                <el-button
                  :icon="Delete"
                  aria-label="删除端口"
                  circle
                  type="danger"
                  @click="manager.handleDeleteBinding(row.port)"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="bindingDialogVisible" align-center class="prototype-dialog" title="绑定新端口" width="460px">
      <el-form class="dialog-form" label-position="top" @submit.prevent="handleSaveBinding">
        <el-form-item label="本地端口">
          <div class="inline-field">
            <el-input-number
              v-model="manager.bindingPort.value"
              :max="manager.stateData.value?.port_max ?? 7999"
              :min="manager.stateData.value?.port_min ?? 7900"
              controls-position="right"
              style="width: 100%"
            />
            <span>剩余: {{ manager.freePortCount.value }} 个</span>
          </div>
        </el-form-item>

        <el-form-item label="目标类型">
          <el-select v-model="manager.bindingMode.value" style="width: 100%">
            <el-option label="代理节点 (Proxy Node)" value="node" />
            <el-option label="内置目标 (DIRECT / AUTO / GLOBAL)" value="builtin" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="manager.bindingMode.value === 'builtin'" label="内置目标">
          <el-select v-model="manager.builtinTarget.value" style="width: 100%">
            <el-option v-for="target in manager.builtinTargets" :key="target" :label="target" :value="target" />
          </el-select>
        </el-form-item>

        <el-form-item v-else label="选择节点">
          <el-select
            v-model="selectedNodeKey"
            filterable
            placeholder="请选择节点"
            style="width: 100%"
            @change="handleNodeSelect"
          >
            <el-option
              v-for="node in manager.filteredNodes.value"
              :key="nodeOptionKey(node)"
              :label="nodeOptionLabel(node)"
              :value="nodeOptionKey(node)"
            />
          </el-select>
          <p class="form-help">可先到节点浏览页筛选订阅、协议和排序。</p>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="bindingDialogVisible = false">取消</el-button>
        <el-button :loading="manager.savingBinding.value" type="primary" @click="handleSaveBinding">
          保存绑定
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Delete, Plus, Promotion, Switch, WarningFilled } from "@element-plus/icons-vue";

import { useGatewayContext } from "@/composables/useGatewayContext";
import type { Binding, NodeItem } from "@/types/gateway";
import type { TagTone } from "@/types/ui";

const manager = useGatewayContext();
const bindingDialogVisible = ref(false);
const selectedNodeKey = ref("");

watch(
  () => manager.selectedNode.value,
  (node) => {
    selectedNodeKey.value = node ? nodeOptionKey(node) : "";
  },
  { immediate: true },
);

const nodeOptions = computed(() => manager.filteredNodes.value);

function openBindingDialog() {
  manager.bindingPort.value = manager.nextFreePort();
  selectedNodeKey.value = manager.selectedNode.value ? nodeOptionKey(manager.selectedNode.value) : "";
  bindingDialogVisible.value = true;
}

function nodeOptionKey(node: NodeItem) {
  return `${node.subscription_id}:${node.id}`;
}

function nodeOptionLabel(node: NodeItem) {
  const delay = manager.nodeDelayLabel(node);
  return `${node.name} · ${node.type || "unknown"} · ${delay}`;
}

function handleNodeSelect(value: string | number | boolean | undefined) {
  if (typeof value !== "string") return;
  const node = nodeOptions.value.find((item) => nodeOptionKey(item) === value);
  if (node) manager.selectNode(node);
}

async function handleSaveBinding() {
  const ok = await manager.handleSaveBinding();
  if (ok) bindingDialogVisible.value = false;
}

function bindingBuiltinType(target: string | undefined): TagTone {
  if (target === "DIRECT") return "success";
  if (target === "REJECT") return "danger";
  return "warning";
}
</script>
