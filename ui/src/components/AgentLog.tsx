import { useEffect, useRef, useState } from 'react';
import type { AgentLogEntry } from '../api/client';
import { useAgentLog } from '../hooks/useResearch';
import { useWebSocket } from '../hooks/useWebSocket';

interface Props {
  researchId: string;
  isActive?: boolean;
}

const TYPE_LABELS: Record<string, string> = {
  text: 'CLAUDE',
  tool_call: 'TOOL',
  tool_result: 'RESULT',
  system: 'SYSTEM',
  error: 'ERROR',
};

const TYPE_COLORS: Record<string, string> = {
  text: 'text-indigo-300',
  tool_call: 'text-yellow-400',
  tool_result: 'text-green-400',
  system: 'text-gray-400',
  error: 'text-red-400',
};

function formatEntry(entry: AgentLogEntry): { label: string; color: string; body: string } {
  const ts = entry.ts ? new Date(entry.ts).toLocaleTimeString('en-US', { hour12: false }) : '??:??:??';
  const phase = typeof entry.meta?.phase === 'string' ? entry.meta.phase.toUpperCase() : null;
  const phaseLabel = phase ? ` [${phase}]` : '';
  const label = `[${ts}]${phaseLabel} [${TYPE_LABELS[entry.type] ?? entry.type.toUpperCase()}]`;
  const color = TYPE_COLORS[entry.type] ?? 'text-gray-300';

  let body = entry.content;
  if (entry.type === 'tool_call') {
    const input = entry.meta?.input as Record<string, unknown> | undefined;
    const preview = input?.command
      ? String(input.command).slice(0, 200)
      : JSON.stringify(input ?? {}).slice(0, 200);
    body = `${entry.content} → ${preview}`;
  } else if (entry.type === 'tool_result') {
    const toolName = entry.meta?.tool_name ? `${entry.meta.tool_name} → ` : '';
    body = toolName + entry.content.slice(0, 500) + (entry.content.length > 500 ? '…' : '');
  }

  return { label, color, body };
}

export default function AgentLog({ researchId, isActive = false }: Props) {
  const { data, isLoading } = useAgentLog(researchId, isActive);
  const { on } = useWebSocket();
  const [lines, setLines] = useState<Array<{ key: number; label: string; color: string; body: string }>>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLPreElement>(null);
  const lineCounter = useRef(0);

  // Initialize from REST response
  useEffect(() => {
    const entries = data?.entries ?? [];
    const formatted = entries.map((entry, index) => {
      const { label, color, body } = formatEntry(entry);
      return {
        key: index,
        label,
        color,
        body,
      };
    });
    lineCounter.current = formatted.length;
    setLines(formatted);
  }, [data?.entries]);

  // Subscribe to real-time WS events
  useEffect(() => {
    if (!isActive) return;
    return on('agent_log', (event) => {
      if (event.research_id !== researchId && event.pipeline_id !== researchId) return;
      const entry = event.entry as AgentLogEntry | undefined;
      if (!entry) return;
      const { label, color, body } = formatEntry(entry);
      setLines((prev) => [...prev, { key: lineCounter.current++, label, color, body }]);
    });
  }, [on, researchId, isActive]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  };

  if (isLoading && lines.length === 0) {
    return <div className="text-gray-500 text-sm">Loading log...</div>;
  }

  if (lines.length === 0) {
    return (
      <div className="text-gray-500 text-sm">
        {isActive ? 'Waiting for agent to start…' : 'No log available.'}
      </div>
    );
  }

  return (
    <div className="relative">
      {isActive && (
        <div className="absolute top-2 right-2 flex items-center gap-1.5 z-10">
          <span className="inline-block w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-green-400">Live</span>
        </div>
      )}
      {!autoScroll && isActive && (
        <button
          onClick={() => {
            setAutoScroll(true);
            if (containerRef.current) {
              containerRef.current.scrollTop = containerRef.current.scrollHeight;
            }
          }}
          className="absolute bottom-10 right-4 z-10 px-3 py-1 rounded bg-indigo-600 text-xs text-white shadow hover:bg-indigo-500"
        >
          ↓ Jump to latest
        </button>
      )}
      <pre
        ref={containerRef}
        onScroll={handleScroll}
        className="bg-gray-900 border border-gray-700 rounded p-4 text-xs font-mono overflow-auto max-h-[600px] whitespace-pre-wrap"
      >
        {lines.map(({ key, label, color, body }) => (
          <span key={key} className="block">
            {label ? (
              <>
                <span className={`${color} select-none`}>{label} </span>
                <span className="text-gray-200">{body}</span>
              </>
            ) : (
              <span className="text-gray-300">{body}</span>
            )}
          </span>
        ))}
      </pre>
    </div>
  );
}
