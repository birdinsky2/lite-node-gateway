import "element-plus/dist/index.css";
import "@/styles/index.css";

import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { createApp } from "vue";

import App from "@/App.vue";

createApp(App).use(ElementPlus, { locale: zhCn }).mount("#app");
