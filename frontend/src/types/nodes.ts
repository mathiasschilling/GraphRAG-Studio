export type NodeType =
  | 'UserInputNode'
  | 'PromptTemplateNode'
  | 'LLMNode'
  | 'DatabaseNode'
  | 'FinalAnswerNode'
  | 'ConditionNode';

export interface NodePosition {
  x: number;
  y: number;
}

export interface NodeConfig {
  prompt?: string;
  system_prompt?: string;
  user_template?: string;
  template?: string;
  model?: string;
  strip_reasoning?: boolean;
  database_id?: string;
  query_template?: string;
  top_k?: number;
  joiner?: string;
  key?: string;
  input_key?: string;
  pass_through_key?: string;
  compare_value?: string;
  operator?: 'lt' | 'gt' | 'eq' | 'neq';
}

export interface NodeDefinition {
  id: string;
  type: NodeType;
  config: NodeConfig;
  position: NodePosition;
}

export interface EdgeDefinition {
  id: string;
  from_node: string;
  from_output: string;
  to_node: string;
  to_input?: string | null;
}

export interface FlowGraph {
  id: string;
  name?: string;
  nodes: Record<string, NodeDefinition>;
  edges: EdgeDefinition[];
}

export interface FlowRead {
  id: string;
  name: string;
  graph: FlowGraph;
  description?: string;
  created_at?: string;
}

export interface NodeRunLog {
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  skipped?: boolean;
}

export type NodeRunStatus = 'idle' | 'pending' | 'running' | 'done' | 'skipped' | 'error';

export interface RunRecord {
  id: string;
  flow_id: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  status?: string;
  input_payload?: Record<string, unknown>;
  output_payload?: Record<string, unknown>;
  node_outputs?: Record<string, NodeRunLog>;
  error?: string | null;
}
