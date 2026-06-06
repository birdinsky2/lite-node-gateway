<template>
  <section class="content-page settings-page">
    <section class="settings-workspace">
      <article class="settings-panel settings-proxy-card">
        <SectionHeading
          eyebrow="Proxy"
          title="系统代理"
          :description="manager.systemProxySelectedLabel.value"
          :icon="SwitchButton"
        />

        <section class="settings-switch-card">
          <div>
            <el-tag :type="manager.systemProxyStatusTone.value" effect="dark">
              {{ manager.systemProxyStatusLabel.value }}
            </el-tag>
            <strong>{{ manager.systemProxy.value.enabled ? "ON" : "OFF" }}</strong>
            <span>{{ manager.systemProxy.value.server }}</span>
          </div>

          <el-switch
            :disabled="!manager.systemProxy.value.helper_ok || manager.savingSystemProxy.value"
            :loading="manager.savingSystemProxy.value"
            :model-value="manager.systemProxy.value.enabled"
            active-text="打开"
            inactive-text="关闭"
            inline-prompt
            size="large"
            @change="handleSwitchChange"
          />
        </section>

        <dl class="settings-facts">
          <div>
            <dt>Helper</dt>
            <dd>{{ manager.systemProxy.value.helper_ok ? "已连接" : helperError }}</dd>
          </div>
          <div>
            <dt>当前节点</dt>
            <dd>{{ manager.systemProxySelectedLabel.value }}</dd>
          </div>
          <div>
            <dt>系统端口</dt>
            <dd>{{ manager.systemProxy.value.server }}</dd>
          </div>
        </dl>

        <div class="settings-actions">
          <el-button :icon="Refresh" :loading="manager.loadingState.value" @click="manager.loadState(true)">
            刷新状态
          </el-button>
          <el-button
            :disabled="!manager.systemProxy.value.helper_ok || !manager.systemProxy.value.selected_resolved"
            :icon="Promotion"
            :loading="manager.probingSystemProxy.value"
            type="primary"
            @click="manager.handleProbeSystemProxy"
          >
            测试出口
          </el-button>
        </div>
      </article>

      <article class="settings-panel settings-form-card">
        <SectionHeading
          eyebrow="Network"
          title="端口与绕过规则"
          description="端口用于 Windows 系统代理，绕过规则会写入 ProxyOverride。"
          :icon="Setting"
        />

        <el-form class="settings-form" label-position="top" @submit.prevent="manager.handleSaveSystemProxySettings">
          <el-form-item label="系统代理端口">
            <el-input-number
              v-model="manager.settingsProxyPort.value"
              :max="65535"
              :min="1"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>

          <el-form-item label="绕过域名和 IP">
            <el-input
              v-model="manager.settingsBypassText.value"
              :autosize="{ minRows: 14, maxRows: 22 }"
              placeholder="一行一条，例如 localhost、127.*、<local>"
              resize="vertical"
              type="textarea"
            />
          </el-form-item>

          <section class="settings-hints">
            <el-tag effect="plain" type="info">一行一条</el-tag>
            <el-tag effect="plain" type="info">保存后写入 Windows</el-tag>
            <el-tag v-if="manager.systemProxy.value.enabled" effect="plain" type="success">当前已开启</el-tag>
          </section>

          <div class="settings-form-actions">
            <el-button :icon="RefreshLeft" @click="manager.handleResetSystemProxyBypass">
              恢复默认绕过
            </el-button>
            <el-button
              :icon="CircleCheck"
              :loading="manager.savingSystemProxySettings.value"
              native-type="submit"
              type="primary"
            >
              保存设置
            </el-button>
          </div>
        </el-form>
      </article>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { CircleCheck, Promotion, Refresh, RefreshLeft, Setting, SwitchButton } from "@element-plus/icons-vue";

import SectionHeading from "@/components/common/SectionHeading.vue";
import { useGatewayContext } from "@/composables/useGatewayContext";

const manager = useGatewayContext();

const helperError = computed(() => manager.systemProxy.value.helper.error || "未连接");

function handleSwitchChange(value: string | number | boolean) {
  void manager.handleToggleSystemProxy(Boolean(value));
}
</script>
