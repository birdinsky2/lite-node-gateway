import type { Component } from "vue";

import type { ViewKey } from "@/router/views";

export type NodeSortMode = "default" | "delay-asc" | "delay-desc";
export type TagTone = "success" | "warning" | "danger" | "info";

export interface NavItem {
  key: ViewKey;
  label: string;
  desc: string;
  longDesc: string;
  icon: Component;
}
