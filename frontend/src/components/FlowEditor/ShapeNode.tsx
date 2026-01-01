import { CSSProperties, memo, useMemo } from 'react';
import { Handle, NodeProps, Position } from 'reactflow';
import type { NodeConfig, NodeType } from '../../types/nodes';
import {
  getConditionFalseKey,
  getConditionTrueKey,
  getNodeInputKey,
  getNodeOutputKey,
} from '../../utils/nodeKeys';

type Shape = 'ellipse' | 'rectangle' | 'rounded' | 'hexagon' | 'diamond';

const shapeByType: Record<string, Shape> = {
  UserInputNode: 'ellipse',
  FinalAnswerNode: 'ellipse',
  PromptTemplateNode: 'rounded',
  LLMNode: 'rectangle',
  DatabaseNode: 'rectangle',
  ConditionNode: 'rectangle',
  ExportNode: 'rectangle',
};

const labelByType: Record<string, string> = {
  UserInputNode: 'Input',
  PromptTemplateNode: 'Prompt',
  LLMNode: 'LLM',
  DatabaseNode: 'Database',
  ConditionNode: 'Condition',
  ExportNode: 'Export',
  FinalAnswerNode: 'Output',
};

const typeBadgeByType: Record<string, string> = {
  UserInputNode: 'Input',
  PromptTemplateNode: 'Prompt',
  LLMNode: 'LLM',
  DatabaseNode: 'DB',
  ConditionNode: 'COND',
  ExportNode: 'Export',
  FinalAnswerNode: 'Output',
};

// Each node type exposes the handles needed to keep default connections intact.
// Sources map to outputs the executor expects (e.g., "prompt" or "response").
type HandleDef = { id: string; position: Position; style?: CSSProperties; label?: string };

const KNOWN_NODE_TYPES = new Set<NodeType>([
  'UserInputNode',
  'PromptTemplateNode',
  'LLMNode',
  'DatabaseNode',
  'ConditionNode',
  'ExportNode',
  'FinalAnswerNode',
]);

const buildHandles = (type: string, config: NodeConfig): { sources: HandleDef[]; targets: HandleDef[] } => {
  const nodeType = type as NodeType;
  switch (nodeType) {
    case 'UserInputNode':
      return {
        sources: [{ id: getNodeOutputKey(nodeType, config), position: Position.Bottom }],
        targets: [],
      };
    case 'PromptTemplateNode':
      return {
        sources: [{ id: getNodeOutputKey(nodeType, config), position: Position.Bottom }],
        targets: [{ id: getNodeInputKey(nodeType, config), position: Position.Top }],
      };
    case 'LLMNode':
      return {
        sources: [{ id: getNodeOutputKey(nodeType, config), position: Position.Bottom }],
        targets: [{ id: getNodeInputKey(nodeType, config), position: Position.Top }],
      };
    case 'DatabaseNode':
      return {
        sources: [{ id: getNodeOutputKey(nodeType, config), position: Position.Bottom }],
        targets: [{ id: getNodeInputKey(nodeType, config), position: Position.Top }],
      };
    case 'ExportNode':
      return {
        sources: [{ id: getNodeOutputKey(nodeType, config), position: Position.Bottom }],
        targets: [{ id: getNodeInputKey(nodeType, config), position: Position.Top }],
      };
    case 'FinalAnswerNode':
      return {
        sources: [],
        targets: [{ id: getNodeInputKey(nodeType, config), position: Position.Top }],
      };
    case 'ConditionNode': {
      const falseKey = getConditionFalseKey(config);
      const trueKey = getConditionTrueKey(config);
      return {
        sources: [
          { id: falseKey, position: Position.Left, label: falseKey, style: { top: '50%' } },
          { id: trueKey, position: Position.Right, label: trueKey, style: { top: '50%' } },
        ],
        targets: [{ id: getNodeInputKey(nodeType, config), position: Position.Top }],
      };
    }
    default:
      return {
        sources: [{ id: 'output', position: Position.Bottom }],
        targets: [{ id: 'input', position: Position.Top }],
      };
  }
};

function uniqueById(handles: HandleDef[]) {
  return Array.from(new Map(handles.map((h) => [h.id, h])).values());
}

function labelStyle(handle: HandleDef): CSSProperties {
  const base: CSSProperties = {
    position: 'absolute',
    fontSize: 11,
    fontWeight: 700,
    color: '#111827',
    pointerEvents: 'none',
  };

  const top = handle.style?.top ?? '50%';
  const left = handle.style?.left;

  switch (handle.position) {
    case Position.Left:
      return { ...base, left: -36, top, transform: 'translateY(-50%)' };
    case Position.Right:
      return { ...base, right: -36, top, transform: 'translateY(-50%)' };
    case Position.Top:
      return { ...base, top: -18, left: left ?? '50%', transform: 'translate(-50%, -50%)' };
    case Position.Bottom:
      return { ...base, bottom: -18, left: left ?? '50%', transform: 'translate(-50%, 50%)' };
    default:
      return base;
  }
}

function shapeClass(shape: Shape) {
  // Map the semantic shape type to the CSS classes that draw the outline.
  switch (shape) {
    case 'ellipse':
      return 'shape-node ellipse';
    case 'rectangle':
      return 'shape-node rectangle';
    case 'rounded':
      return 'shape-node rounded';
    case 'hexagon':
      return 'shape-node hexagon';
    case 'diamond':
      return 'shape-node diamond';
    default:
      return 'shape-node rectangle';
  }
}

const ShapeNode = memo(({ data, selected }: NodeProps) => {
  // Render a UML-inspired node with dedicated handles for normal and
  // conditional connections. The memo wrapper avoids re-renders when
  // selection changes elsewhere on the canvas.
  const shape = useMemo(() => shapeByType[data?.type as string] ?? 'rectangle', [data?.type]);
  const config = (data?.config || {}) as NodeConfig;
  const typeLabel = labelByType[data?.type as string] ?? (data?.type as string) ?? 'Node';
  const typeBadge = typeBadgeByType[data?.type as string] ?? typeLabel;
  const customName = (config.name || '').trim();
  const label = customName || typeLabel;
  const customHandles = buildHandles(data?.type as string, config);
  const runStatus = (data?.status as string) || 'idle';
  const statusLabel = runStatus.charAt(0).toUpperCase() + runStatus.slice(1);
  const statusClass = `status-${runStatus}`;
  const isKnownType = KNOWN_NODE_TYPES.has((data?.type as NodeType) || 'UserInputNode');
  const highlightRole = (data?.highlightRole as string) || '';

  const targetHandles = uniqueById(
    customHandles.targets.length ? customHandles.targets : isKnownType ? [] : [{ id: 'input', position: Position.Top }],
  );
  const sourceHandles = uniqueById(
    customHandles.sources.length ? customHandles.sources : isKnownType ? [] : [{ id: 'output', position: Position.Bottom }],
  );

  return (
    <div
      className={`${shapeClass(shape)} ${statusClass}`}
      data-run-status={runStatus}
      data-selected={selected ? 'true' : 'false'}
      data-highlight={highlightRole || undefined}
    >
      <div className={`shape-status-badge ${statusClass}`}>{statusLabel}</div>
      {targetHandles.map((handle) => (
        <div key={`t-${handle.id}`}>
          <Handle id={handle.id} type="target" position={handle.position} style={handle.style} />
          {handle.label && <span style={labelStyle(handle)}>{handle.label}</span>}
        </div>
      ))}
      <div className="shape-label">{label}</div>
      <div className="shape-type-label">{typeBadge}</div>
      {sourceHandles.map((handle) => (
        <div key={`s-${handle.id}`}>
          <Handle id={handle.id} type="source" position={handle.position} style={handle.style} />
          {handle.label && <span style={labelStyle(handle)}>{handle.label}</span>}
        </div>
      ))}
    </div>
  );
});

ShapeNode.displayName = 'ShapeNode';

export default ShapeNode;
