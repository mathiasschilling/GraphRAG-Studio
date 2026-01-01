import { useEffect, useMemo, useState } from 'react';
import type { KeyUsageEntry, NodeRunLog, RunRecord } from '../../types/nodes';

interface Props {
  run: RunRecord | null;
  selectedNodeId?: string | null;
  onKeyHover?: (key: string | null) => void;
}

const formatDuration = (value?: number) => {
  if (value === undefined || Number.isNaN(value)) return '–';
  return `${value.toFixed(1)} ms`;
};

const renderNodeLog = (nodeId: string, log: NodeRunLog) => {
  const isSkipped = log.skipped;
  return (
    <div key={nodeId} style={{ padding: '8px 0', borderTop: '1px solid #e2e8f0' }}>
      <div className="flex-between" style={{ alignItems: 'baseline' }}>
        <strong>{nodeId}</strong>
        <span style={{ color: isSkipped ? '#b91c1c' : '#475569', fontSize: 12 }}>
          {isSkipped ? 'Skipped' : 'Completed'} {log.duration_ms !== undefined && !isSkipped ? `(${formatDuration(log.duration_ms)})` : ''}
        </span>
      </div>
      <div style={{ fontSize: 12, color: '#475569', marginBottom: 4 }}>
        {log.started_at ? `Started at ${log.started_at}` : 'Start time unavailable'}
        {log.completed_at ? ` · Completed at ${log.completed_at}` : ''}
      </div>
      <div style={{ marginBottom: 4 }}>
        <div style={{ fontWeight: 600 }}>Inputs</div>
        <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(log.inputs ?? {}, null, 2)}</pre>
      </div>
      <div>
        <div style={{ fontWeight: 600 }}>Outputs</div>
        <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(log.outputs ?? {}, null, 2)}</pre>
      </div>
    </div>
  );
};

const formatKeyValue = (value: unknown) => {
  if (value === null || value === undefined) return 'n/a';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
};

export default function RunResultPanel({ run, selectedNodeId, onKeyHover }: Props) {
  // Render the most recent run output alongside per-node execution details.
  if (!run) {
    return (
      <div style={{ marginTop: 10 }}>
        <h4 style={{ marginBottom: 6 }}>Last run</h4>
        <div className="run-result">
          <p style={{ margin: 0, color: '#475569' }}>Run the flow to view results.</p>
        </div>
      </div>
    );
  }

  const nodeOutputs = run.node_outputs || {};
  const keyUsageEntries = useMemo(() => {
    const entries = Object.entries(run.key_usage || {}) as Array<[string, KeyUsageEntry]>;
    return entries.sort(([a], [b]) => a.localeCompare(b));
  }, [run.key_usage]);
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);

  useEffect(() => {
    setHoveredKey(null);
    onKeyHover?.(null);
  }, [run.id, onKeyHover]);
  const sortedNodeEntries = Object.entries(nodeOutputs).sort(([, a], [, b]) => {
    const first = a?.started_at ? new Date(a.started_at).getTime() : 0;
    const second = b?.started_at ? new Date(b.started_at).getTime() : 0;
    return first - second;
  });

  const selectedLog = selectedNodeId ? nodeOutputs[selectedNodeId] : null;
  const hoveredEntry = hoveredKey ? run.key_usage?.[hoveredKey] : null;

  return (
    <div style={{ marginTop: 10 }}>
      <h4 style={{ marginBottom: 6 }}>Last run</h4>
      <div className="run-result">
        <div style={{ fontSize: 12, color: '#475569', marginBottom: 4 }}>
          Status: {run.status || 'completed'}
        </div>
        <div style={{ marginBottom: 8 }}>
          <strong>Run output</strong>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(run.output_payload ?? {}, null, 2)}</pre>
          {run.error && <div style={{ color: 'red' }}>{run.error}</div>}
        </div>

        <div style={{ marginBottom: 12 }}>
          <strong>Key usage</strong>
          {!keyUsageEntries.length ? (
            <p style={{ margin: '4px 0 0', color: '#475569' }}>No keys recorded for this run.</p>
          ) : (
            <div
              className="key-usage-grid"
              onMouseLeave={() => {
                setHoveredKey(null);
                onKeyHover?.(null);
              }}
            >
              <div className="key-usage-list">
                {keyUsageEntries.map(([key, entry]) => (
                  <div
                    key={key}
                    className={`key-usage-item ${hoveredKey === key ? 'active' : ''}`}
                    onMouseEnter={() => {
                      setHoveredKey(key);
                      onKeyHover?.(key);
                    }}
                  >
                    <div className="key-usage-name">{key}</div>
                    <div className="key-usage-meta">
                      {entry.source_node ? `from ${entry.source_node}` : 'no origin'}
                    </div>
                  </div>
                ))}
              </div>
              <div className="key-usage-detail">
                {hoveredEntry ? (
                  <>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>{hoveredKey}</div>
                    <div style={{ fontSize: 12, color: '#475569', marginBottom: 6 }}>
                      {hoveredEntry.source_node ? `Origin: ${hoveredEntry.source_node}` : 'Origin: none'}
                    </div>
                    <div style={{ fontSize: 12, color: '#475569', marginBottom: 6 }}>
                      Consumers: {(hoveredEntry.consumers || []).join(', ') || 'none'}
                    </div>
                    <pre className="key-usage-value">{formatKeyValue(hoveredEntry.value)}</pre>
                  </>
                ) : (
                  <p style={{ margin: 0, color: '#475569' }}>
                    Hover a key to view its value and highlight connected nodes.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        <div>
          <strong>Node details</strong>
          {!Object.keys(nodeOutputs).length && (
            <p style={{ margin: '4px 0 0', color: '#475569' }}>
              No node outputs were recorded for this run.
            </p>
          )}
          {selectedNodeId ? (
            selectedLog ? (
              renderNodeLog(selectedNodeId, selectedLog)
            ) : (
              <p style={{ margin: '4px 0 0', color: '#475569' }}>
                This node was added after the last run or did not execute.
              </p>
            )
          ) : (
            sortedNodeEntries.map(([nodeId, log]) => renderNodeLog(nodeId, log))
          )}
        </div>
      </div>
    </div>
  );
}
