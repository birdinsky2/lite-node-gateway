<template>
  <article class="port-compose">
    <SectionHeading eyebrow="Expose" title="开放端口" :description="manager.selectedTargetLabel.value" :icon="Link" />

    <div v-if="manager.selectedNodeBindings.value.length" class="selected-opened">
      <span>当前节点已开放</span>
      <div>
        <el-tag v-for="binding in manager.selectedNodeBindings.value" :key="binding.port" effect="plain" type="success">
          {{ binding.port }}
        </el-tag>
      </div>
    </div>

    <el-form class="stack-form" label-position="top" @submit.prevent="manager.handleSaveBinding">
      <el-form-item label="端口">
        <el-input-number
          v-model="manager.bindingPort.value"
          :max="manager.stateData.value?.port_max ?? 7999"
          :min="manager.stateData.value?.port_min ?? 7900"
          controls-position="right"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="模式">
        <el-radio-group v-model="manager.bindingMode.value" class="mode-switch">
          <el-radio-button label="node">节点</el-radio-button>
          <el-radio-button label="builtin">内置</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="manager.bindingMode.value === 'builtin'" label="内置目标">
        <el-select v-model="manager.builtinTarget.value" style="width: 100%">
          <el-option v-for="target in manager.builtinTargets" :key="target" :label="target" :value="target" />
        </el-select>
      </el-form-item>

      <el-button :icon="CircleCheck" :loading="manager.savingBinding.value" native-type="submit" type="primary">
        保存端口
      </el-button>
    </el-form>
  </article>
</template>

<script setup lang="ts">
import { CircleCheck, Link } from "@element-plus/icons-vue";

import { useGatewayContext } from "@/composables/useGatewayContext";
import SectionHeading from "@/components/common/SectionHeading.vue";

const manager = useGatewayContext();
</script>
