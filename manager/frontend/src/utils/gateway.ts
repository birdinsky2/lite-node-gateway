import type { NodeItem } from "@/types/gateway";

export function bindingKey(subscriptionId: string, nodeId: string) {
  return `${subscriptionId}:${nodeId}`;
}

export function nodeKey(node: NodeItem) {
  return bindingKey(node.subscription_id, node.id);
}
