interface Props {
  current: string | null;
  proposed: string;
}

export default function ConfigDiff({ current, proposed }: Props) {
  const currentLines = (current ?? '(no existing config)').split('\n');
  const proposedLines = proposed.split('\n');

  return (
    <div className="grid grid-cols-2 gap-4 text-xs font-mono">
      <div>
        <div className="text-gray-400 mb-1 text-sm font-sans">Current</div>
        <pre className="bg-gray-900 border border-gray-700 rounded p-3 overflow-auto max-h-80 text-gray-400">
          {currentLines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </pre>
      </div>
      <div>
        <div className="text-gray-400 mb-1 text-sm font-sans">Proposed</div>
        <pre className="bg-gray-900 border border-green-900/50 rounded p-3 overflow-auto max-h-80 text-green-300">
          {proposedLines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </pre>
      </div>
    </div>
  );
}
