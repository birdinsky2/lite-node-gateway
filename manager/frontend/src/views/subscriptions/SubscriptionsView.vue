<template>
  <section class="prototype-page subscriptions-page">
    <header class="prototype-page-header">
      <div>
        <h1>订阅管理</h1>
        <p>管理您的代理节点订阅源</p>
      </div>
      <el-button :icon="Plus" type="primary" @click="importDialogVisible = true">
        添加订阅
      </el-button>
    </header>

    <section class="prototype-card table-card">
      <el-table :data="manager.subscriptions.value" empty-text="暂未导入任何订阅" stripe>
        <el-table-column label="名称" min-width="180">
          <template #default="{ row }: { row: Subscription }">
            <strong class="table-primary-text">{{ row.name }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="订阅地址" min-width="260">
          <template #default="{ row }: { row: Subscription }">
            <code class="table-code" :title="row.url_masked">{{ row.url_masked }}</code>
          </template>
        </el-table-column>
        <el-table-column label="节点数" prop="node_count" width="110" />
        <el-table-column label="最后更新" min-width="170">
          <template #default="{ row }: { row: Subscription }">
            <span class="muted-text">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }: { row: Subscription }">
            <div class="status-stack">
              <el-tag :type="row.last_error ? 'danger' : 'success'" effect="light">
                {{ row.last_error ? "失败" : "已更新" }}
              </el-tag>
              <small v-if="row.last_error">{{ row.last_error }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column align="right" label="操作" width="210">
          <template #default="{ row }: { row: Subscription }">
            <div class="table-actions">
              <el-tooltip content="查看节点">
                <el-button :icon="Monitor" aria-label="查看节点" circle @click="manager.openSubscriptionNodes(row.id)" />
              </el-tooltip>
              <el-tooltip content="刷新">
                <el-button
                  :icon="Refresh"
                  :loading="manager.refreshingId.value === row.id"
                  aria-label="刷新订阅"
                  circle
                  @click="manager.handleRefreshSubscription(row.id)"
                />
              </el-tooltip>
              <el-tooltip content="删除">
                <el-button
                  :icon="Delete"
                  aria-label="删除订阅"
                  circle
                  type="danger"
                  @click="manager.handleDeleteSubscription(row.id)"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="importDialogVisible" align-center class="prototype-dialog" title="导入订阅" width="520px">
      <el-form class="dialog-form" label-position="top" @submit.prevent="handleImport">
        <el-form-item label="名称">
          <el-input v-model="manager.subscriptionForm.name" clearable placeholder="例如：我的高级节点" />
        </el-form-item>
        <el-form-item label="订阅地址 (URL)">
          <el-input
            v-model="manager.subscriptionForm.url"
            :autosize="{ minRows: 4, maxRows: 7 }"
            clearable
            placeholder="https://..."
            type="textarea"
          />
          <p class="form-help">支持单个订阅链接。</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button :loading="manager.creatingSubscription.value" type="primary" @click="handleImport">
          保存并导入
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Delete, Monitor, Plus, Refresh } from "@element-plus/icons-vue";

import { useGatewayContext } from "@/composables/useGatewayContext";
import type { Subscription } from "@/types/gateway";
import { formatDate } from "@/utils/date";

const manager = useGatewayContext();
const importDialogVisible = ref(false);

async function handleImport() {
  const ok = await manager.handleCreateSubscription();
  if (ok) importDialogVisible.value = false;
}
</script>
