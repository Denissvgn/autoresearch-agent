// Harness capability surfaces: selection, diagnostics, run context, and
// cursor-based reconnect. Everything renders from API descriptors — the
// tests assert there are no branches on harness names.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import HarnessPicker from '../HarnessPicker';
import HarnessContextPanel from '../HarnessContextPanel';
import type { HarnessContext, HarnessDescriptor } from '../../api/client';

function descriptor(overrides: Partial<HarnessDescriptor> = {}): HarnessDescriptor {
  return {
    name: 'fixture-harness',
    version: '2.1.0',
    contract_version: 'autoresearch_harness.v1',
    capabilities: ['pause'],
    unsupported_capabilities: [
      { capability: 'resume', reason: 'not advertised by this harness; refused explicitly' },
      { capability: 'steering', reason: 'not advertised by this harness; refused explicitly' },
    ],
    preflight: {
      checks: [
        { name: 'identity', status: 'ok', detail: 'fixture 2.1.0' },
        { name: 'executable', status: 'unknown', detail: 'no probe' },
      ],
    },
    ...overrides,
  };
}

describe('HarnessPicker renders descriptors without name branches', () => {
  it('lists harnesses, capabilities, refusals, and preflight statuses', () => {
    const harnesses = [
      descriptor(),
      descriptor({ name: 'other-thing', capabilities: [], version: '0.1.0' }),
    ];
    render(<HarnessPicker harnesses={harnesses} selected="other-thing" onSelect={() => {}} />);
    expect(screen.getByTestId('harness-option-fixture-harness')).toBeTruthy();
    expect(screen.getByTestId('harness-option-other-thing')).toBeTruthy();
    // the selected harness's diagnostics come from its own descriptor
    expect(screen.getByTestId('no-optional-capabilities')).toBeTruthy();
    expect(screen.getByTestId('unsupported-resume').textContent).toContain('refused explicitly');
    expect(screen.getByTestId('preflight-identity').getAttribute('data-status')).toBe('ok');
  });

  it('surfaces preflight problems and supported capabilities for a capable harness', () => {
    render(<HarnessPicker harnesses={[descriptor()]} selected="fixture-harness" onSelect={() => {}} />);
    expect(screen.getByTestId('capability-pause').textContent).toContain('supported');
    // an unknown preflight state is visibly unknown, never assumed ok
    expect(screen.getByTestId('preflight-executable').getAttribute('data-status')).toBe('unknown');
    expect(screen.getByTestId('preflight-executable').textContent).toContain('unknown');
  });

  it('reports the selection through the callback', () => {
    const onSelect = vi.fn();
    render(
      <HarnessPicker
        harnesses={[descriptor(), descriptor({ name: 'second' })]}
        selected="fixture-harness"
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByLabelText(/second/i));
    expect(onSelect).toHaveBeenCalledWith('second');
  });
});

function context(overrides: Partial<HarnessContext> = {}): HarnessContext {
  return {
    research_id: 'res-1',
    harness: descriptor(),
    resume_mode: 'continuation',
    evidence: {
      authority_counts: {
        receipt_verified: 2,
        unverified_imported: 1,
        model_proposed: 3,
      },
      verified: true,
      imported: 1,
    },
    candidate_evaluator_context: {
      evaluator: 'receipt-authoritative',
      candidate_digest: 'abc123',
    },
    usage_quality: {
      cost_known_usd: 1.25,
      cost_unknown_events: 2,
      total_usage_events: 5,
      cost_status: 'partial',
    },
    viewer: { kind: 'scoped', subject: 'agent-1', permissions: ['read', 'lifecycle'] },
    lifecycle: {
      actions: [
        { action: 'pause', enabled: true, reason: '' },
        {
          action: 'resume',
          enabled: false,
          reason: "this harness does not advertise 'resume'; the control is refused explicitly",
        },
        { action: 'stop', enabled: true, reason: '' },
        {
          action: 'promote',
          enabled: false,
          reason: "the caller's credential lacks 'promote'",
        },
      ],
    },
    ...overrides,
  };
}

describe('HarnessContextPanel: provenance, usage, and honest controls', () => {
  it('shows evidence authority, evaluator context, and resume mode', () => {
    render(<HarnessContextPanel context={context()} />);
    expect(screen.getByTestId('ctx-resume-mode').textContent).toBe('continuation');
    expect(screen.getByTestId('ctx-evidence').textContent).toContain('verified (2)');
    expect(screen.getByTestId('ctx-evidence').textContent).toContain('imported: 1');
    expect(screen.getByTestId('ctx-candidate').textContent).toContain('receipt-authoritative');
    expect(screen.getByTestId('ctx-candidate').textContent).toContain('abc123');
    expect(screen.getByTestId('ctx-viewer').textContent).toContain('scoped');
  });

  it('makes unknown cost visibly unknown and partial cost honest', () => {
    const { rerender } = render(<HarnessContextPanel context={context()} />);
    const usage = screen.getByTestId('ctx-usage');
    expect(usage.textContent).toContain('$1.2500 known');
    expect(usage.textContent).toContain('2 unknown-cost');
    // a fully unknown cost is labeled unknown, never rendered as zero
    rerender(
      <HarnessContextPanel
        context={context({
          usage_quality: {
            cost_known_usd: 0,
            cost_unknown_events: 3,
            total_usage_events: 3,
            cost_status: 'unknown',
          },
        })}
      />,
    );
    expect(screen.getByTestId('ctx-usage').textContent).toBe('cost unknown');
  });

  it('disables unsupported controls with their explanations', () => {
    const onAction = vi.fn();
    render(<HarnessContextPanel context={context()} onAction={onAction} />);
    const pause = screen.getByTestId('lifecycle-pause') as HTMLButtonElement;
    const resume = screen.getByTestId('lifecycle-resume') as HTMLButtonElement;
    const promote = screen.getByTestId('lifecycle-promote') as HTMLButtonElement;
    expect(pause.disabled).toBe(false);
    expect(resume.disabled).toBe(true);
    expect(promote.disabled).toBe(true);
    expect(screen.getByTestId('lifecycle-resume-reason').textContent).toContain(
      'refused explicitly',
    );
    expect(screen.getByTestId('lifecycle-promote-reason').textContent).toContain(
      "lacks 'promote'",
    );
    fireEvent.click(pause);
    expect(onAction).toHaveBeenCalledWith('pause');
    fireEvent.click(resume);
    expect(onAction).not.toHaveBeenCalledWith('resume');
  });
});

// ── cursor-based reconnect ────────────────────────────────────
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((msg: { data: string }) => void) | null = null;
  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  close() {
    this.onclose?.();
  }
}

describe('useWebSocket cursor-based reconnect and resync', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('replays from the last cursor and resyncs after a reconnect', async () => {
    const { default: React } = await import('react');
    const { act } = await import('@testing-library/react');
    const { WebSocketProvider, useWebSocket } = await import('../../hooks/useWebSocket');

    const seen: Array<{ type: string; [k: string]: unknown }> = [];
    function Probe() {
      const { on } = useWebSocket();
      React.useEffect(() => on('*', (e) => seen.push(e)), [on]);
      return null;
    }
    await act(async () => {
      render(
        <WebSocketProvider>
          <Probe />
        </WebSocketProvider>,
      );
    });
    const first = MockWebSocket.instances[0];
    expect(first.url).not.toContain('cursor=');
    await act(async () => {
      first.onopen?.();
      first.onmessage?.({ data: JSON.stringify({ type: 'iteration_complete', sequence: 7 }) });
    });
    vi.useFakeTimers();
    await act(async () => {
      first.onclose?.();
      vi.advanceTimersByTime(3100);
    });
    vi.useRealTimers();
    const second = MockWebSocket.instances[1];
    // cursor-based reconnect: the URL carries the last seen sequence
    expect(second.url).toContain('cursor=7');
    await act(async () => {
      second.onopen?.();
    });
    // reconnection restores authoritative state through a resync signal
    const resyncs = seen.filter((e) => e.type === 'resync');
    expect(resyncs.length).toBeGreaterThanOrEqual(1);
    expect(resyncs[0].reason).toBe('reconnected');
  });

  it('turns an expired-cursor catchup plan into a resync', async () => {
    const { default: React } = await import('react');
    const { act } = await import('@testing-library/react');
    const { WebSocketProvider, useWebSocket } = await import('../../hooks/useWebSocket');

    const seen: Array<{ type: string; [k: string]: unknown }> = [];
    function Probe() {
      const { on } = useWebSocket();
      React.useEffect(() => on('*', (e) => seen.push(e)), [on]);
      return null;
    }
    await act(async () => {
      render(
        <WebSocketProvider>
          <Probe />
        </WebSocketProvider>,
      );
    });
    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.onopen?.();
      ws.onmessage?.({
        data: JSON.stringify({ type: 'catchup', mode: 'resync', reason: 'cursor_expired' }),
      });
    });
    const resyncs = seen.filter((e) => e.type === 'resync');
    expect(resyncs.some((e) => e.reason === 'cursor_expired')).toBe(true);
  });
});