import { CSSProperties, memo, useMemo } from 'react';
import { Handle, NodeProps, Position } from 'reactflow';

type Shape = 'ellipse' | 'rectangle' | 'rounded' | 'hexagon' | 'diamond';

const shapeByType: Record<string, Shape> = {
  UserInputNode: 'ellipse',
  FinalAnswerNode: 'ellipse',
  PromptTemplateNode: 'rounded',
  LLMNode: 'rectangle',
  DatabaseNode: 'rectangle',
  ConditionNode: 'rectangle',
};

const labelByType: Record<string, string> = {
  UserInputNode: 'Input',
  PromptTemplateNode: 'Prompt',
  LLMNode: 'LLM',
  DatabaseNode: 'Database',
  ConditionNode: 'Condition',
  FinalAnswerNode: 'Output',
};

// Each node type exposes the handles needed to keep default connections intact.
// Sources map to outputs the executor expects (e.g., "prompt" or "response").
type HandleDef = { id: string; position: Position; style?: CSSProperties; label?: string };

const handleConfig: Record<string, { sources: HandleDef[]; targets: HandleDef[] }> = {
  UserInputNode: {
    sources: [{ id: 'input', position: Position.Bottom }],
    targets: [],
  },
  PromptTemplateNode: {
    sources: [{ id: 'prompt', position: Position.Bottom }],
    targets: [{ id: 'input', position: Position.Top }],
  },
  LLMNode: {
    sources: [{ id: 'response', position: Position.Bottom }],
    targets: [{ id: 'prompt', position: Position.Top }],
  },
  DatabaseNode: {
    sources: [{ id: 'response', position: Position.Bottom }],
    targets: [{ id: 'query', position: Position.Top }],
  },
  FinalAnswerNode: {
    sources: [],
    targets: [{ id: 'response', position: Position.Top }],
  },
  ConditionNode: {
    sources: [
      { id: 'false', position: Position.Left, label: 'false', style: { top: '50%' } },
      { id: 'true', position: Position.Right, label: 'true', style: { top: '50%' } },
    ],
    targets: [{ id: 'input', position: Position.Top }],
  },
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
  const label = labelByType[data?.type as string] ?? (data?.type as string) ?? 'Node';
  const customHandles = handleConfig[data?.type as string];
  const runStatus = (data?.status as string) || 'idle';
  const statusLabel = runStatus.charAt(0).toUpperCase() + runStatus.slice(1);
  const statusClass = `status-${runStatus}`;
  const handles =
    customHandles ?? ({
      sources: [{ id: 'output', position: Position.Bottom }],
      targets: [{ id: 'input', position: Position.Top }],
    } as const);

  const targetHandles = uniqueById(
    handles.targets.length ? handles.targets : customHandles ? [] : [{ id: 'input', position: Position.Top }],
  );
  const sourceHandles = uniqueById(
    handles.sources.length ? handles.sources : customHandles ? [] : [{ id: 'output', position: Position.Bottom }],
  );

  return (
    <div className={`${shapeClass(shape)} ${statusClass}`} data-run-status={runStatus} data-selected={selected ? 'true' : 'false'}>
      <div className={`shape-status-badge ${statusClass}`}>{statusLabel}</div>
      {targetHandles.map((handle) => (
        <div key={`t-${handle.id}`}>
          <Handle id={handle.id} type="target" position={handle.position} style={handle.style} />
          {handle.label && <span style={labelStyle(handle)}>{handle.label}</span>}
        </div>
      ))}
      <div className="shape-label">{label}</div>
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
