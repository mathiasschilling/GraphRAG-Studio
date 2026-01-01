import type { NodeType } from '../../types/nodes';

const PALETTE_NODES: Array<{ type: NodeType; label: string }> = [
  { type: 'UserInputNode', label: 'Input' },
  { type: 'LLMNode', label: 'LLM' },
  { type: 'DatabaseNode', label: 'Database' },
  { type: 'ConditionNode', label: 'Condition' },
  { type: 'ExportNode', label: 'Export' },
  { type: 'FinalAnswerNode', label: 'Output' },
];

interface Props {
  onAddNode: (type: NodeType) => void;
  missingOutputNotice?: boolean;
}

export default function NodePalette({ onAddNode, missingOutputNotice = false }: Props) {
  // Simple palette of the supported node types, rendered as buttons so users
  // can quickly drop new nodes onto the canvas.
  return (
    <div>
      <h3>Node palette</h3>
      <p>Select a node type to add it to the canvas.</p>
      <div className="palette-grid">
        {PALETTE_NODES.map(({ type, label }) => (
          <button key={type} className="button" onClick={() => onAddNode(type)}>
            {label}
          </button>
        ))}
      </div>

      {missingOutputNotice && (
        <div className="banner warning" style={{ marginTop: 12 }}>
          <div style={{ marginBottom: 6 }}>Add an Output node to expose your final answer.</div>
          <button className="button" onClick={() => onAddNode('FinalAnswerNode')}>
            + Add Output node
          </button>
        </div>
      )}
    </div>
  );
}
