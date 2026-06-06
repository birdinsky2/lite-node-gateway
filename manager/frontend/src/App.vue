<template>
  <el-config-provider :locale="zhCn">
    <AdminLayout />
  </el-config-provider>
</template>

<script setup lang="ts">
import zhCn from "element-plus/es/locale/lang/zh-cn";

import { provideGatewayManager } from "@/composables/useGatewayContext";
import AdminLayout from "@/layouts/AdminLayout.vue";

provideGatewayManager();
</script>
