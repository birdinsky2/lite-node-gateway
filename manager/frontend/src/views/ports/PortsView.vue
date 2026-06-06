<template>
  <section class="content-page ports-page">
    <section class="ports-workspace">
      <NodeWorkbench />

      <aside class="port-side">
        <PortComposePanel />
        <BindingListPanel />
      </aside>
    </section>
  </section>
</template>

<script setup lang="ts">
import BindingListPanel from "@/views/ports/components/BindingListPanel.vue";
import NodeWorkbench from "@/views/ports/components/NodeWorkbench.vue";
import PortComposePanel from "@/views/ports/components/PortComposePanel.vue";
</script>
