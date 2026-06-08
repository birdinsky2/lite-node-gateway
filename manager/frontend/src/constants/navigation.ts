import { DataBoard, Link, Management, Monitor, Setting } from "@element-plus/icons-vue";

import type { NavItem } from "@/types/ui";

export const navItems: NavItem[] = [
  {
    key: "dashboard",
    label: "系统概览",
    desc: "实时状态",
    longDesc: "Lite Node Gateway 的实时状态、核心连接和端口池使用情况。",
    icon: DataBoard,
  },
  {
    key: "subscriptions",
    label: "订阅管理",
    desc: "导入与维护",
    longDesc: "集中管理多个订阅地址，查看节点数量、刷新订阅并快速进入节点视图。",
    icon: Management,
  },
  {
    key: "nodes",
    label: "节点浏览",
    desc: "搜索与选择",
    longDesc: "浏览订阅中的代理节点，筛选协议、测速，并选择节点用于端口绑定或系统代理。",
    icon: Monitor,
  },
  {
    key: "ports",
    label: "端口绑定",
    desc: "本地映射",
    longDesc: "将节点或内置目标暴露到本地固定端口，并查看每个代理地址的可用状态。",
    icon: Link,
  },
  {
    key: "settings",
    label: "设置",
    desc: "端口与绕过",
    longDesc: "快速开关系统代理，调整系统代理端口，并维护宿主机代理绕过域名和 IP 规则。",
    icon: Setting,
  },
];
