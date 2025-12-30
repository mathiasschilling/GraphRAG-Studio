import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useEffect } from 'react';
import { Position, type NodeProps } from 'reactflow';

import ShapeNode from './ShapeNode';
import { RunStateProvider, useRunState } from '../../state/runState';
import type { RunEvent } from '../../types/runs';

function buildNodeProps(status: string): NodeProps {
  return {
    id: 'node-1',
    type: 'shape',
    data: { type: 'UserInputNode', status },
    dragging: false,
    dragHandle: undefined,
    selected: false,
    xPos: 0,
    yPos: 0,
    targetPosition: Position.Top,
    sourcePosition: Position.Bottom,
    zIndex: 0,
    isConnectable: true,
    isConnectableStart: true,
    isConnectableEnd: true,
    deletable: true,
    draggable: true,
    selectable: true,
    hidden: false,
  } as unknown as NodeProps;
}

function Harness() {
  const { beginRun, ingestEvent, nodeStatuses } = useRunState();

  useEffect(() => {
    beginRun('run-1', ['node-1']);
  }, [beginRun]);

  const dispatch = (event: RunEvent) => ingestEvent(event);
  const status = nodeStatuses['node-1'] ?? 'idle';

  return (
    <div>
      <button
        onClick={() => dispatch({
          run_id: 'run-1',
          node_id: 'node-1',
          status: 'started',
          sequence: 0,
          timestamp: new Date().toISOString(),
        })}
      >
        start
      </button>
      <button
        onClick={() => dispatch({
          run_id: 'run-1',
          node_id: 'node-1',
          status: 'completed',
          sequence: 1,
          timestamp: new Date().toISOString(),
        })}
      >
        complete
      </button>
      <button
        onClick={() => {
          beginRun('run-2', ['node-1']);
          dispatch({
            run_id: 'run-2',
            node_id: 'node-1',
            status: 'skipped',
            sequence: 0,
            timestamp: new Date().toISOString(),
          });
        }}
      >
        restart-skip
      </button>
      <div data-testid="shape-wrapper">
        <ShapeNode {...buildNodeProps(status)} />
      </div>
    </div>
  );
}

describe('ShapeNode run-state styling', () => {
  it('updates status as events progress', async () => {
    render(
      <RunStateProvider>
        <Harness />
      </RunStateProvider>,
    );

    const shape = () => screen.getByTestId('shape-wrapper').querySelector('.shape-node');

    expect(shape()).toHaveAttribute('data-run-status', 'pending');
    expect(screen.getByText('Pending')).toBeInTheDocument();

    fireEvent.click(screen.getByText('start'));
    await waitFor(() => expect(shape()).toHaveAttribute('data-run-status', 'running'));
    expect(screen.getByText('Running')).toBeInTheDocument();

    fireEvent.click(screen.getByText('complete'));
    await waitFor(() => expect(shape()).toHaveAttribute('data-run-status', 'done'));
    expect(screen.getByText('Done')).toBeInTheDocument();
  });

  it('resets to pending for a new run and shows skipped nodes distinctly', async () => {
    render(
      <RunStateProvider>
        <Harness />
      </RunStateProvider>,
    );

    fireEvent.click(screen.getByText('restart-skip'));
    await waitFor(() =>
      expect(screen.getByTestId('shape-wrapper').querySelector('.shape-node')).toHaveAttribute(
        'data-run-status',
        'skipped',
      ),
    );
    expect(screen.getByText('Skipped')).toBeInTheDocument();
  });
});
