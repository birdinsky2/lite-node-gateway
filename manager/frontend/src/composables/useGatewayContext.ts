import { inject, provide, type InjectionKey } from "vue";

import { useGatewayManager, type GatewayManager } from "@/composables/useGatewayManager";

const gatewayManagerKey: InjectionKey<GatewayManager> = Symbol("gateway-manager");

export function provideGatewayManager() {
  const manager = useGatewayManager();
  provide(gatewayManagerKey, manager);
  return manager;
}

export function useGatewayContext() {
  const manager = inject(gatewayManagerKey);
  if (!manager) {
    throw new Error("Gateway manager context is not provided.");
  }
  return manager;
}
