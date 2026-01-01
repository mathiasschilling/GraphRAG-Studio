import { useCallback, useEffect, useMemo, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import ReactFlow, {
  Background,
  Controls,
  Edge,
  Node,
  addEdge,
  Connection,
  useEdgesState,
  useNodesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { databasesApi } from '../api/databases';
import { flowsApi } from '../api/flows';
import { modelsApi } from '../api/models';
import { runsApi } from '../api/runs';
import {
  RunRecord,
  NodeDefinition,
  EdgeDefinition,
  FlowGraph,
  NodeType,
  FlowRead,
  NodeConfig,
} from '../types/nodes';
import type { VectorDatabase } from '../types/databases';
import { RunEvent } from '../types/runs';
import NodePalette from '../components/FlowEditor/NodePalette';
import NodeConfigPanel from '../components/FlowEditor/NodeConfigPanel';
import RunResultPanel from '../components/FlowEditor/RunResultPanel';
import ShapeNode from '../components/FlowEditor/ShapeNode';
import { RunStateProvider, useRunState } from '../state/runState';
import { useRunEventStream } from '../hooks/useRunEventStream';
import {
  getConditionFalseKey,
  getConditionTrueKey,
  getNodeInputKey,
  getNodeOutputKey,
} from '../utils/nodeKeys';

const nodeTypes = { shape: ShapeNode };

const MIN_LEFT_WIDTH = 220;
const MAX_LEFT_WIDTH = 520;
const MIN_RIGHT_WIDTH = 240;
const MAX_RIGHT_WIDTH = 560;
const STORAGE_KEY = 'flow-editor-layout';

type LayoutPrefs = {
  isLeftOpen?: boolean;
  isRightOpen?: boolean;
  leftWidth?: number;
  rightWidth?: number;
};

function getStoredLayout(): LayoutPrefs | null {
  if (typeof window === 'undefined') return null;

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as LayoutPrefs) : null;
  } catch (error) {
    console.warn('Failed to read layout preferences', error);
    return null;
  }
}

function toReactFlowNodes(nodes: Record<string, NodeDefinition>): Node[] {
  // Convert persisted node definitions into React Flow nodes while preserving
  // positions and configs for the custom shape renderer.
  return Object.values(nodes).map((node) => ({
    id: node.id,
    position: node.position,
    data: { label: node.type, config: node.config, type: node.type, status: 'idle' },
    type: 'shape',
  }));
}

const DEFAULT_CONFIGS: Record<NodeType, NodeConfig> = {
  UserInputNode: { key: 'input' },
  PromptTemplateNode: { template: 'Hello {input}' },
  LLMNode: {
    model: 'llama3',
    system_prompt: 'You are a helpful assistant.',
    user_template: 'Answer the user message: {input}',
    strip_reasoning: false,
  },
  DatabaseNode: {
    database_id: '',
    input_key: 'query',
    query_template: '',
    top_k: 5,
  },
  FinalAnswerNode: { key: 'response' },
  ConditionNode: { input_key: 'input', pass_through_key: '', compare_value: '', operator: 'eq' },
};

function toReactFlowEdges(edges: EdgeDefinition[], nodes: Record<string, NodeDefinition>): Edge[] {
  // Map backend edge definitions to React Flow edges, carrying handle names
  // so custom ports stay aligned with node data.
  return edges.map((edge) => {
    const targetNode = nodes[edge.to_node];
    const targetType = targetNode?.type as NodeType | undefined;
    const targetConfig = (targetNode?.config || {}) as NodeConfig;
    const sourceNode = nodes[edge.from_node];
    const sourceType = sourceNode?.type as NodeType | undefined;
    const sourceConfig = (sourceNode?.config || {}) as NodeConfig;
    return {
      id: edge.id,
      source: edge.from_node,
      target: edge.to_node,
      sourceHandle: edge.from_output || getNodeOutputKey(sourceType || 'UserInputNode', sourceConfig),
      targetHandle: edge.to_input || getNodeInputKey(targetType || 'PromptTemplateNode', targetConfig),
    };
  });
}

function toFlowGraph(flowId: string, nodes: Node[], edges: Edge[]): FlowGraph {
  // Transform the in-memory React Flow state back into the API shape for
  // saving and execution.
  const nodeMap: Record<string, NodeDefinition> = {};
  nodes.forEach((node) => {
    nodeMap[node.id] = {
      id: node.id,
      type: (node.data?.type as NodeType) ?? 'UserInputNode',
      config: node.data?.config || {},
      position: node.position,
    };
  });

  const nodeTypeMap = nodes.reduce<Record<string, NodeType>>((acc, node) => {
    const nodeType = (node.data?.type as NodeType) || 'UserInputNode';
    acc[node.id] = nodeType;
    return acc;
  }, {});

  const nodeConfigMap = nodes.reduce<Record<string, NodeConfig>>((acc, node) => {
    acc[node.id] = (node.data?.config || {}) as NodeConfig;
    return acc;
  }, {});

  const edgeDefs: EdgeDefinition[] = edges.map((edge) => {
    const targetType = nodeTypeMap[edge.target] || 'PromptTemplateNode';
    const sourceType = nodeTypeMap[edge.source] || 'UserInputNode';
    return {
      id: edge.id,
      from_node: edge.source,
      from_output: edge.sourceHandle || getNodeOutputKey(sourceType, nodeConfigMap[edge.source]),
      to_node: edge.target,
      to_input: edge.targetHandle || getNodeInputKey(targetType, nodeConfigMap[edge.target]),
    };
  });

  return { id: flowId, nodes: nodeMap, edges: edgeDefs };
}

function FlowEditorContent() {
  const { flowId = '' } = useParams();
  const queryClient = useQueryClient();
  const { data: flow, isLoading } = useQuery<FlowRead>({
    queryKey: ['flow', flowId],
    queryFn: () => flowsApi.get(flowId),
    enabled: Boolean(flowId),
  });

  const { data: availableModels } = useQuery<string[]>({
    queryKey: ['models'],
    queryFn: () => modelsApi.list(),
  });

  const { data: availableDatabases } = useQuery<VectorDatabase[]>({
    queryKey: ['databases'],
    queryFn: () => databasesApi.list(),
  });

  const storedLayout = useMemo(() => getStoredLayout(), []);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([]);
  const [runInput, setRunInput] = useState('');
  const [lastRun, setLastRun] = useState<RunRecord | null>(null);
  const [flowName, setFlowName] = useState('');
  const [isLeftOpen, setIsLeftOpen] = useState(storedLayout?.isLeftOpen ?? true);
  const [isRightOpen, setIsRightOpen] = useState(storedLayout?.isRightOpen ?? true);
  const [leftWidth, setLeftWidth] = useState(storedLayout?.leftWidth ?? 280);
  const [rightWidth, setRightWidth] = useState(storedLayout?.rightWidth ?? 320);

  const { activeRunId, nodeStatuses, beginRun, registerNodes, ingestEvent, reset } = useRunState();

  const hasOutputNode = useMemo(() => nodes.some((node) => node.data?.type === 'FinalAnswerNode'), [nodes]);

  useEffect(() => {
    // Reset run tracking when switching flows so stale runs don't leak into the new graph
    reset();
  }, [flowId, reset]);

  useEffect(() => {
    // Populate the canvas when a flow is fetched or refetched.
    if (flow?.graph) {
      setNodes(toReactFlowNodes(flow.graph.nodes));
      setEdges(toReactFlowEdges(flow.graph.edges, flow.graph.nodes));
    }
    if (flow?.name) {
      setFlowName(flow.name);
    }
  }, [flow, setNodes, setEdges]);

  useEffect(() => {
    registerNodes(nodes.map((node) => node.id));
  }, [nodes, registerNodes]);

  useEffect(() => {
    // Remember the sidebar visibility and widths across reloads so the user
    // keeps their preferred layout.
    if (typeof window === 'undefined') return;

    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ isLeftOpen, isRightOpen, leftWidth, rightWidth }),
    );
  }, [isLeftOpen, isRightOpen, leftWidth, rightWidth]);

  useEffect(() => {
    // Guard against persisted widths drifting outside the allowed range.
    setLeftWidth((current) => Math.min(Math.max(current, MIN_LEFT_WIDTH), MAX_LEFT_WIDTH));
    setRightWidth((current) => Math.min(Math.max(current, MIN_RIGHT_WIDTH), MAX_RIGHT_WIDTH));
  }, []);

  useEffect(() => {
    // Thread live node statuses into React Flow so the shapes re-render as events arrive.
    setNodes((current) =>
      current.map((node) => ({
        ...node,
        data: {
          ...node.data,
          status: nodeStatuses[node.id] ?? (activeRunId ? 'pending' : (node.data?.status as string) ?? 'idle'),
        },
      })),
    );
  }, [nodeStatuses, activeRunId, setNodes]);

  const saveFlow = useMutation({
    // Persist the current graph state back to the backend.
    mutationFn: (payload: FlowGraph) => flowsApi.save(flowId, { name: flowName, graph: payload }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['flow', flowId], updated);
      queryClient.invalidateQueries({ queryKey: ['flows'] });
      setFlowName(updated.name);
    },
  });

  const runFlow = useMutation({
    // Execute the currently loaded flow using the user-provided run input.
    mutationFn: () => flowsApi.run(flowId, { text: runInput }),
    onSuccess: (run) => {
      beginRun(run.id, nodes.map((node) => node.id));
      setLastRun(run);
    },
  });

  const onConnect = (connection: Connection) => {
    // Normalize edge handles so connections fall back to each node's default ports.
    const sourceNode = nodes.find((n) => n.id === connection.source);
    const targetNode = nodes.find((n) => n.id === connection.target);
    const conn: Connection = { ...connection };

    const sourceType = (sourceNode?.data?.type as NodeType) || 'UserInputNode';
    const targetType = (targetNode?.data?.type as NodeType) || 'PromptTemplateNode';
    const sourceConfig = (sourceNode?.data?.config || {}) as NodeConfig;
    const targetConfig = (targetNode?.data?.config || {}) as NodeConfig;

    conn.sourceHandle = conn.sourceHandle || getNodeOutputKey(sourceType, sourceConfig);
    conn.targetHandle = conn.targetHandle || getNodeInputKey(targetType, targetConfig);

    setEdges((eds) => addEdge({ ...conn, id: `${conn.source}-${conn.target}-${Date.now()}` }, eds));
  };

  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedNodeId) || null, [nodes, selectedNodeId]);

  const handleSelectionChange = useCallback(
    ({ nodes: selectedNodes, edges: selectedEdges }: { nodes: Node[]; edges: Edge[] }) => {
      setSelectedNodeId(selectedNodes[0]?.id ?? null);
      setSelectedEdgeIds(selectedEdges.map((edge) => edge.id));
    },
    [],
  );

  const beginResize = (event: ReactPointerEvent<HTMLDivElement>, side: 'left' | 'right') => {
    event.preventDefault();
    const startX = event.clientX;

    const initialWidth = side === 'left' ? leftWidth : rightWidth;
    if (side === 'left') setIsLeftOpen(true);
    if (side === 'right') setIsRightOpen(true);

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const delta = moveEvent.clientX - startX;
      if (side === 'left') {
        const next = Math.min(Math.max(initialWidth + delta, MIN_LEFT_WIDTH), MAX_LEFT_WIDTH);
        setLeftWidth(next);
      } else {
        const next = Math.min(Math.max(initialWidth - delta, MIN_RIGHT_WIDTH), MAX_RIGHT_WIDTH);
        setRightWidth(next);
      }
    };

    const handlePointerUp = () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  const handleNodeUpdate = (id: string, config: Record<string, unknown>) => {
    // Update a node's config while keeping other properties intact.
    const previous = nodes.find((node) => node.id === id);
    const prevType = (previous?.data?.type as NodeType) || 'UserInputNode';
    const prevConfig = (previous?.data?.config || {}) as NodeConfig;
    const nextConfig = config as NodeConfig;

    const prevSourceHandle = getNodeOutputKey(prevType, prevConfig);
    const nextSourceHandle = getNodeOutputKey(prevType, nextConfig);
    const prevTargetHandle = getNodeInputKey(prevType, prevConfig);
    const nextTargetHandle = getNodeInputKey(prevType, nextConfig);
    const prevTrueHandle = prevType === 'ConditionNode' ? getConditionTrueKey(prevConfig) : null;
    const prevFalseHandle = prevType === 'ConditionNode' ? getConditionFalseKey(prevConfig) : null;
    const nextTrueHandle = prevType === 'ConditionNode' ? getConditionTrueKey(nextConfig) : null;
    const nextFalseHandle = prevType === 'ConditionNode' ? getConditionFalseKey(nextConfig) : null;

    setNodes((nds) =>
      nds.map((node) =>
        node.id === id ? { ...node, data: { ...node.data, config } } : node,
      ),
    );

    if (
      prevSourceHandle !== nextSourceHandle ||
      prevTargetHandle !== nextTargetHandle ||
      prevTrueHandle !== nextTrueHandle ||
      prevFalseHandle !== nextFalseHandle
    ) {
      setEdges((eds) =>
        eds.map((edge) => {
          if (edge.source === id) {
            if (prevType === 'ConditionNode') {
              if (edge.sourceHandle === prevTrueHandle) {
                return { ...edge, sourceHandle: nextTrueHandle || edge.sourceHandle };
              }
              if (edge.sourceHandle === prevFalseHandle) {
                return { ...edge, sourceHandle: nextFalseHandle || edge.sourceHandle };
              }
            } else if (edge.sourceHandle === prevSourceHandle) {
              return { ...edge, sourceHandle: nextSourceHandle };
            }
          }
          if (edge.target === id && edge.targetHandle === prevTargetHandle) {
            return { ...edge, targetHandle: nextTargetHandle };
          }
          return edge;
        }),
      );
    }
  };

  const handleAddNode = (type: NodeType) => {
    // Spawn a new node with a deterministic label and slight positional offset
    // so newly added nodes don't stack on top of each other.
    const id = `${type}-${Date.now()}`;
    const position = { x: 150 + nodes.length * 30, y: 80 + nodes.length * 30 };
    setNodes((nds) => [
      ...nds,
      {
        id,
        position,
        data: { label: type, config: DEFAULT_CONFIGS[type] ?? {}, type },
        type: 'shape',
      },
    ]);
  };

  const handleSave = () => {
    // Convert the React Flow state to the API payload and dispatch a save.
    const payload = toFlowGraph(flow?.graph.id || flowId, nodes, edges);
    saveFlow.mutate(payload);
  };

  const handleDeleteNode = useCallback(
    (id: string) => {
      // Remove the node, any connected edges, and clear selection when deleted
      // via the panel button or keyboard shortcut.
      setNodes((nds) => nds.filter((node) => node.id !== id));
      setEdges((eds) => eds.filter((edge) => edge.source !== id && edge.target !== id));
      setSelectedNodeId((current) => (current === id ? null : current));
      setSelectedEdgeIds([]);
    },
    [setEdges, setNodes],
  );

  useEffect(() => {
    // Enable Delete-key removal for the currently selected elements.
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Delete') {
        event.preventDefault();
        if (selectedEdgeIds.length > 0) {
          setEdges((eds) => eds.filter((edge) => !selectedEdgeIds.includes(edge.id)));
          setSelectedEdgeIds([]);
        } else if (selectedNodeId) {
          handleDeleteNode(selectedNodeId);
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedNodeId, selectedEdgeIds, handleDeleteNode]);

  const handleTerminalEvent = useCallback(
    async (event: RunEvent) => {
      const completedRun = await runsApi.get(event.run_id);
      setLastRun(completedRun);
      queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
    [queryClient],
  );

  useRunEventStream(activeRunId, ingestEvent, handleTerminalEvent);

  const showLeftToggle = !isLeftOpen;
  const showRightToggle = !isRightOpen;
  const gridTemplateColumns = `${isLeftOpen ? `${leftWidth}px` : '0px'} 12px 1fr 12px ${
    isRightOpen ? `${rightWidth}px` : '0px'
  }`;

  if (isLoading || !flow) {
    return <p>Loading flow…</p>;
  }

  return (
    <div className="flow-editor-layout" style={{ gridTemplateColumns }}>
      <div
        className={`panel ${isLeftOpen ? '' : 'collapsed'}`}
        style={{ width: isLeftOpen ? leftWidth : 0 }}
        aria-hidden={!isLeftOpen}
      >
        {isLeftOpen && (
          <>
            <div className="flex-between" style={{ alignItems: 'flex-start', marginBottom: 8 }}>
              <div>
                <label htmlFor="flow-name" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                  Flow name
                </label>
                <input
                  id="flow-name"
                  className="input"
                  style={{ width: '100%', minWidth: 200 }}
                  value={flowName}
                  onChange={(e) => setFlowName(e.target.value)}
                />
                <p style={{ margin: '6px 0 0', color: '#475569' }}>Build and run your flow.</p>
              </div>
              <button className="icon-button" aria-label="Hide left panel" onClick={() => setIsLeftOpen(false)}>
                ✕
              </button>
            </div>

            <NodePalette onAddNode={handleAddNode} missingOutputNotice={!hasOutputNode} />
            <div style={{ marginTop: 16 }}>
              <label htmlFor="run-input">Run input</label>
              <textarea
                id="run-input"
                className="textarea"
                placeholder="Enter user input"
                value={runInput}
                onChange={(e) => setRunInput(e.target.value)}
              />
              <button
                className="button"
                style={{ width: '100%', marginTop: 8 }}
                onClick={() => runFlow.mutate()}
                disabled={runFlow.isPending}
              >
                Run flow
              </button>
              {runFlow.error && <p style={{ color: 'red' }}>Failed to run flow</p>}
              <RunResultPanel run={lastRun} selectedNodeId={selectedNodeId} />
            </div>
          </>
        )}
      </div>

      <div
        className={`resize-handle ${isLeftOpen ? '' : 'collapsed'}`}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize left panel"
        onPointerDown={(event) => beginResize(event, 'left')}
      >
        <span className="handle-grip" />
      </div>

      <div className="panel" style={{ minWidth: 0 }}>
        <div className="reactflow-wrapper">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onSelectionChange={handleSelectionChange}
            onPaneClick={() => {
              setSelectedNodeId(null);
              setSelectedEdgeIds([]);
            }}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
      </div>

      <div
        className={`resize-handle ${isRightOpen ? '' : 'collapsed'}`}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize right panel"
        onPointerDown={(event) => beginResize(event, 'right')}
      >
        <span className="handle-grip" />
      </div>

      <div
        className={`panel ${isRightOpen ? '' : 'collapsed'}`}
        style={{ width: isRightOpen ? rightWidth : 0 }}
        aria-hidden={!isRightOpen}
      >
        {isRightOpen && (
          <>
            <div className="flex-between" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>Configuration</h3>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="icon-button" aria-label="Hide right panel" onClick={() => setIsRightOpen(false)}>
                  ✕
                </button>
                <button className="button secondary" onClick={handleSave} disabled={saveFlow.isPending}>
                  Save flow
                </button>
              </div>
            </div>
            {selectedNode ? (
              <>
                <NodeConfigPanel
                  node={selectedNode}
                  onChange={handleNodeUpdate}
                  availableModels={availableModels}
                  availableDatabases={availableDatabases}
                />
                <button
                  className="button danger"
                  style={{ width: '100%', marginTop: 8 }}
                  onClick={() => handleDeleteNode(selectedNode.id)}
                >
                  Delete node
                </button>
              </>
            ) : (
              <p>Select a node to edit its settings.</p>
            )}
          </>
        )}
      </div>

      {showLeftToggle && (
        <button className="panel-toggle left" onClick={() => setIsLeftOpen(true)}>
          Show left panel
        </button>
      )}

      {showRightToggle && (
        <button className="panel-toggle right" onClick={() => setIsRightOpen(true)}>
          Show right panel
        </button>
      )}
    </div>
  );
}

export default function FlowEditorPage() {
  return (
    <RunStateProvider>
      <FlowEditorContent />
    </RunStateProvider>
  );
}
