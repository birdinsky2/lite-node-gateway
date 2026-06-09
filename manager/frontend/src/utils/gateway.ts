import type { NodeDelayResult, NodeItem } from "@/types/gateway";

export function bindingKey(subscriptionId: string, nodeId: string) {
  return `${subscriptionId}:${nodeId}`;
}

export function nodeKey(node: NodeItem) {
  return bindingKey(node.subscription_id, node.id);
}

export function nodeDelayResultKey(result: NodeDelayResult) {
  return result.subscription_id ? bindingKey(result.subscription_id, result.node_id) : result.node_id;
}
