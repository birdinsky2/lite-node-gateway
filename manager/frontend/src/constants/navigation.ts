import { Management, Monitor, Setting, SwitchButton } from "@element-plus/icons-vue";

import type { NavItem } from "@/types/ui";

export const navItems: NavItem[] = [
  {
    key: "subscriptions",
    label: "订阅管理",
    desc: "导入与维护",
    longDesc: "集中管理多个订阅地址，查看节点数量、刷新订阅并快速进入节点视图。",
    icon: Management,
  },
  {
    key: "ports",
    label: "代理端口",
    desc: "节点与端口",
    longDesc: "选择订阅中的节点，将不同节点开放到不同本地端口，并查看端口映射状态。",
    icon: Monitor,
  },
  {
    key: "system-proxy",
    label: "系统代理",
    desc: "本机上网开关",
    longDesc: "选择订阅节点并控制宿主机系统代理，让本机流量通过当前节点出口。",
    icon: SwitchButton,
  },
  {
    key: "settings",
    label: "设置",
    desc: "端口与绕过",
    longDesc: "快速开关系统代理，调整系统代理端口，并维护宿主机代理绕过域名和 IP 规则。",
    icon: Setting,
  },
];
