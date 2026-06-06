<template>
  <article class="import-surface">
    <SectionHeading eyebrow="Subscription" title="导入订阅" :icon="Upload" />

    <el-form class="stack-form" label-position="top" @submit.prevent="manager.handleCreateSubscription">
      <el-form-item label="名称">
        <el-input v-model="manager.subscriptionForm.name" clearable placeholder="例如：机场 A" />
      </el-form-item>
      <el-form-item label="订阅地址">
        <el-input
          v-model="manager.subscriptionForm.url"
          :autosize="{ minRows: 5, maxRows: 7 }"
          clearable
          placeholder="https://..."
          type="textarea"
        />
      </el-form-item>
      <el-button :icon="Plus" :loading="manager.creatingSubscription.value" native-type="submit" type="primary">
        导入订阅
      </el-button>
    </el-form>
  </article>
</template>

<script setup lang="ts">
import { Plus, Upload } from "@element-plus/icons-vue";

import { useGatewayContext } from "@/composables/useGatewayContext";
import SectionHeading from "@/components/common/SectionHeading.vue";

const manager = useGatewayContext();
</script>
