import { onMounted } from "vue";

import { useGatewayActions } from "@/composables/gateway/actions";
import { useGatewayDerived } from "@/composables/gateway/derived";
import { createGatewayState } from "@/composables/gateway/state";

export function useGatewayManager() {
  const state = createGatewayState();
  const derived = useGatewayDerived(state);
  const actions = useGatewayActions(state, derived);

  onMounted(() => {
    void actions.loadState();
  });

  return {
    ...state,
    ...derived,
    ...actions,
  };
}

export type GatewayManager = ReturnType<typeof useGatewayManager>;
