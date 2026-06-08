<template>
  <section class="prototype-page dashboard-page">
    <header class="prototype-page-header">
      <div>
        <h1>系统概览</h1>
        <p>Lite Node Gateway 的实时状态</p>
      </div>
      <div class="prototype-page-actions">
        <el-button :icon="Refresh" :loading="manager.loadingState.value" @click="manager.loadState(true)">
          刷新
        </el-button>
        <el-button :icon="Switch" :loading="manager.rebuilding.value" type="primary" @click="manager.handleRebuild">
          重载配置
        </el-button>
      </div>
    </header>

    <section class="dashboard-metrics" aria-label="系统状态指标">
      <article class="metric-card">
        <div>
          <span>Mihomo 核心</span>
          <el-icon :class="manager.stateData.value?.core.ok ? 'tone-success' : 'tone-danger'">
            <TrendCharts />
          </el-icon>
        </div>
        <strong>{{ manager.stateData.value?.core.ok ? "运行中" : "未连接" }}</strong>
        <p>{{ manager.coreVersion.value }}</p>
      </article>

      <article class="metric-card">
        <div>
          <span>订阅数量</span>
          <el-icon><Management /></el-icon>
        </div>
        <strong>{{ manager.subscriptions.value.length }}</strong>
        <p>已导入的订阅列表</p>
      </article>

      <article class="metric-card">
        <div>
          <span>可用节点</span>
          <el-icon><Monitor /></el-icon>
        </div>
        <strong>{{ manager.totalNodeCount.value }}</strong>
        <p>包含所有订阅</p>
      </article>

      <article class="metric-card">
        <div>
          <span>已绑定端口</span>
          <el-icon><Link /></el-icon>
        </div>
        <strong>{{ manager.bindings.value.length }}</strong>
        <p>激活的本地映射</p>
      </article>
    </section>

    <section class="dashboard-grid">
      <article class="prototype-card">
        <header class="prototype-card-header">
          <h2>网络配置</h2>
        </header>
        <dl class="detail-list">
          <div>
            <dt>主代理端口</dt>
            <dd>{{ manager.systemProxy.value.server_port }}</dd>
          </div>
          <div>
            <dt>固定端口池</dt>
            <dd>{{ manager.portRange.value }}</dd>
          </div>
          <div>
            <dt>Manager 服务</dt>
            <dd class="inline-status">
              <el-icon class="tone-success"><CircleCheck /></el-icon>
              运行中
            </dd>
          </div>
        </dl>
      </article>

      <article class="prototype-card">
        <header class="prototype-card-header">
          <h2>系统代理</h2>
        </header>
        <dl class="detail-list">
          <div>
            <dt>状态</dt>
            <dd>
              <el-tag :type="manager.systemProxyStatusTone.value" effect="light">
                {{ manager.systemProxyStatusLabel.value }}
              </el-tag>
            </dd>
          </div>
          <div>
            <dt>当前节点</dt>
            <dd>{{ manager.systemProxySelectedLabel.value }}</dd>
          </div>
          <div>
            <dt>本机代理</dt>
            <dd>{{ manager.systemProxy.value.server }}</dd>
          </div>
        </dl>
      </article>
    </section>
  </section>
</template>

<script setup lang="ts">
import { CircleCheck, DataBoard as Management, Link, Monitor, Refresh, Switch, TrendCharts } from "@element-plus/icons-vue";

import { useGatewayContext } from "@/composables/useGatewayContext";

const manager = useGatewayContext();
</script>
