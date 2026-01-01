import type { NodeConfig, NodeType } from '../types/nodes';

const normalizeKey = (value: unknown, fallback: string) => {
  if (typeof value !== 'string') {
    return fallback;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
};

export const DEFAULT_OUTPUT_KEYS: Record<NodeType, string> = {
  UserInputNode: 'input',
  PromptTemplateNode: 'prompt',
  LLMNode: 'response',
  DatabaseNode: 'response',
  FinalAnswerNode: 'output',
  ConditionNode: 'true',
};

export const DEFAULT_INPUT_KEYS: Record<NodeType, string> = {
  UserInputNode: 'input',
  PromptTemplateNode: 'input',
  LLMNode: 'prompt',
  DatabaseNode: 'query',
  FinalAnswerNode: 'response',
  ConditionNode: 'input',
};

export const getConditionTrueKey = (config: NodeConfig = {}) =>
  normalizeKey(config.true_key, DEFAULT_OUTPUT_KEYS.ConditionNode);

export const getConditionFalseKey = (config: NodeConfig = {}) =>
  normalizeKey(config.false_key, 'false');

export const getNodeOutputKey = (type: NodeType, config: NodeConfig = {}) => {
  switch (type) {
    case 'UserInputNode':
      return normalizeKey(config.key, DEFAULT_OUTPUT_KEYS.UserInputNode);
    case 'PromptTemplateNode':
    case 'LLMNode':
    case 'DatabaseNode':
    case 'FinalAnswerNode':
      return normalizeKey(config.output_key, DEFAULT_OUTPUT_KEYS[type]);
    case 'ConditionNode':
      return getConditionTrueKey(config);
    default:
      return DEFAULT_OUTPUT_KEYS.UserInputNode;
  }
};

export const getNodeInputKey = (type: NodeType, config: NodeConfig = {}) => {
  switch (type) {
    case 'DatabaseNode':
    case 'ConditionNode':
      return normalizeKey(config.input_key, DEFAULT_INPUT_KEYS[type]);
    case 'FinalAnswerNode':
      return normalizeKey(config.key, DEFAULT_INPUT_KEYS.FinalAnswerNode);
    case 'UserInputNode':
      return normalizeKey(config.key, DEFAULT_INPUT_KEYS.UserInputNode);
    case 'PromptTemplateNode':
    case 'LLMNode':
      return DEFAULT_INPUT_KEYS[type];
    default:
      return DEFAULT_INPUT_KEYS.PromptTemplateNode;
  }
};
