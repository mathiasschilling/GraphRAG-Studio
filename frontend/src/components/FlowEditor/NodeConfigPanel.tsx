import { useMemo } from 'react';
import type { Node } from 'reactflow';
import type { NodeConfig, NodeType } from '../../types/nodes';
import type { VectorDatabase } from '../../types/databases';

interface Props {
  node: Node;
  onChange: (id: string, config: NodeConfig) => void;
  availableModels?: string[];
  availableDatabases?: VectorDatabase[];
}

const editableConfig: Record<NodeType, Array<{ key: keyof NodeConfig; label: string; placeholder?: string }>> = {
  UserInputNode: [{ key: 'key', label: 'Output key', placeholder: 'input' }],
  PromptTemplateNode: [
    { key: 'template', label: 'Prompt template', placeholder: 'Hello {input}' },
  ],
  LLMNode: [
    { key: 'system_prompt', label: 'System prompt', placeholder: 'You are a helpful assistant.' },
    { key: 'user_template', label: 'User message template', placeholder: 'Answer the user message: {input}' },
    { key: 'model', label: 'Model name', placeholder: 'e.g. mistral' },
    { key: 'strip_reasoning', label: 'Strip reasoning tokens' },
  ],
  FinalAnswerNode: [{ key: 'key', label: 'Answer input key', placeholder: 'response' }],
  DatabaseNode: [
    { key: 'database_id', label: 'Database' },
    { key: 'query_template', label: 'Query template', placeholder: 'Find context for: {input}' },
    { key: 'input_key', label: 'Input key', placeholder: 'query' },
    { key: 'top_k', label: 'Top K', placeholder: '5' },
  ],
  ConditionNode: [
    { key: 'input_key', label: 'Input key to check', placeholder: 'input' },
    { key: 'pass_through_key', label: 'Pass-through key (optional)', placeholder: 'input' },
    { key: 'compare_value', label: 'Compare against value', placeholder: '5' },
    { key: 'operator', label: 'Operator' },
  ],
};

export default function NodeConfigPanel({ node, onChange, availableModels, availableDatabases }: Props) {
  // Render dynamic configuration fields based on the selected node's type.
  const config = (node.data?.config || {}) as NodeConfig;
  const type = (node.data?.type as NodeType) || 'UserInputNode';
  const fields = useMemo(() => {
    const seen = new Set<string>();
    return (editableConfig[type] || []).filter((field) => {
      if (seen.has(field.key)) return false;
      seen.add(field.key);
      return true;
    });
  }, [type]);

  if (!fields.length) {
    return <p>No configurable fields for this node.</p>;
  }

  const renderField = (field: { key: keyof NodeConfig; label: string; placeholder?: string }) => {
    // Condition nodes use a select for operators; other fields default to textareas
    // so multi-line prompt templates remain easy to edit.
    if (type === 'ConditionNode' && field.key === 'operator') {
      return (
        <div key={field.key} style={{ marginBottom: 10 }}>
          <label htmlFor={`${node.id}-${field.key}`}>{field.label}</label>
          <select
            id={`${node.id}-${field.key}`}
            className="textarea"
            value={(config as Record<string, string>)[field.key] || 'eq'}
            onChange={(e) => onChange(node.id, { ...config, [field.key]: e.target.value })}
          >
            <option value="gt">greater than</option>
            <option value="lt">less than</option>
            <option value="eq">equal to</option>
            <option value="neq">not equal to</option>
          </select>
        </div>
      );
    }

    if (type === 'LLMNode' && field.key === 'model' && availableModels && availableModels.length > 0) {
      return (
        <div key={field.key} style={{ marginBottom: 10 }}>
          <label htmlFor={`${node.id}-${field.key}`}>{field.label}</label>
          <select
            id={`${node.id}-${field.key}`}
            className="textarea"
            value={(config as Record<string, string>)[field.key] || availableModels[0]}
            onChange={(e) => onChange(node.id, { ...config, [field.key]: e.target.value })}
          >
            {availableModels.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>
      );
    }

    if (type === 'LLMNode' && field.key === 'strip_reasoning') {
      return (
        <div key={field.key} style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            id={`${node.id}-${field.key}`}
            type="checkbox"
            checked={Boolean((config as Record<string, boolean>)[field.key])}
            onChange={(e) => onChange(node.id, { ...config, [field.key]: e.target.checked })}
          />
          <label htmlFor={`${node.id}-${field.key}`}>{field.label}</label>
        </div>
      );
    }

    if (type === 'DatabaseNode' && field.key === 'database_id') {
      const databases = availableDatabases ?? [];
      return (
        <div key={field.key} style={{ marginBottom: 10 }}>
          <label htmlFor={`${node.id}-${field.key}`}>{field.label}</label>
          {databases.length > 0 ? (
            <select
              id={`${node.id}-${field.key}`}
              className="textarea"
              value={(config as Record<string, string>)[field.key] || ''}
              onChange={(e) => onChange(node.id, { ...config, [field.key]: e.target.value })}
            >
              <option value="" disabled>
                Select a database
              </option>
              {databases.map((database) => (
                <option key={database.id} value={database.id}>
                  {database.name}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={`${node.id}-${field.key}`}
              className="input"
              placeholder="Database ID"
              value={(config as Record<string, string>)[field.key] || ''}
              onChange={(e) => onChange(node.id, { ...config, [field.key]: e.target.value })}
            />
          )}
        </div>
      );
    }

    if (type === 'DatabaseNode' && field.key === 'top_k') {
      return (
        <div key={field.key} style={{ marginBottom: 10 }}>
          <label htmlFor={`${node.id}-${field.key}`}>{field.label}</label>
          <input
            id={`${node.id}-${field.key}`}
            className="input"
            type="number"
            min={1}
            value={(config as Record<string, number>)[field.key] ?? 5}
            onChange={(e) =>
              onChange(node.id, {
                ...config,
                [field.key]: e.target.value === '' ? undefined : Number(e.target.value),
              })
            }
          />
        </div>
      );
    }

    return (
      <div key={field.key} style={{ marginBottom: 10 }}>
        <label htmlFor={`${node.id}-${field.key}`}>{field.label}</label>
        <textarea
          id={`${node.id}-${field.key}`}
          className="textarea"
          placeholder={field.placeholder}
          value={
            type === 'LLMNode' && field.key === 'user_template'
              ? (config as Record<string, string>)[field.key] || (config as Record<string, string>).prompt || ''
              : (config as Record<string, string>)[field.key] || ''
          }
          onChange={(e) => onChange(node.id, { ...config, [field.key]: e.target.value })}
        />
      </div>
    );
  };

  return (
    <div>
      <h4 style={{ marginTop: 0 }}>{type}</h4>
      {fields.map((field) => renderField(field))}
      {(type === 'PromptTemplateNode' || type === 'LLMNode' || type === 'DatabaseNode') && (
        <p style={{ color: '#475569', marginTop: 0 }}>
          Use <code>{'{input}'}</code> or other handle names to pull upstream values into your
          prompt. Inputs are collected from connected handles and exposed as template variables.
        </p>
      )}
    </div>
  );
}
