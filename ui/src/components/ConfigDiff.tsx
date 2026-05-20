interface Props {
  current: string | null;
  proposed: string;
}

function diffLines(one: string[], two: string[]) {
  const matrix: number[][] = Array(one.length + 1)
    .fill(null)
    .map(() => Array(two.length + 1).fill(0));

  for (let i = 1; i <= one.length; i++) {
    for (let j = 1; j <= two.length; j++) {
      if (one[i - 1] === two[j - 1]) {
        matrix[i][j] = matrix[i - 1][j - 1] + 1;
      } else {
        matrix[i][j] = Math.max(matrix[i - 1][j], matrix[i][j - 1]);
      }
    }
  }

  let i = one.length;
  let j = two.length;
  const result: Array<{ type: 'added' | 'removed' | 'same'; value: string }> = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && one[i - 1] === two[j - 1]) {
      result.unshift({ type: 'same', value: one[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || matrix[i][j - 1] >= matrix[i - 1][j])) {
      result.unshift({ type: 'added', value: two[j - 1] });
      j--;
    } else {
      result.unshift({ type: 'removed', value: one[i - 1] });
      i--;
    }
  }
  return result;
}

export default function ConfigDiff({ current, proposed }: Props) {
  const currentLines = (current ?? '').split('\n');
  const proposedLines = proposed.split('\n');
  const diff = diffLines(currentLines, proposedLines);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-gray-400 font-sans px-1">
        <span>Configuration Diff</span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-red-950 border border-red-800 rounded-sm"></span>
            Removed
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-emerald-950 border border-emerald-800 rounded-sm"></span>
            Added
          </span>
        </div>
      </div>
      <div className="bg-gray-950 border border-gray-800 rounded overflow-hidden">
        <pre className="text-xs font-mono p-3 overflow-auto max-h-96 leading-relaxed select-all selection:bg-indigo-500/30">
          {diff.map((line, idx) => {
            if (line.type === 'added') {
              return (
                <div key={idx} className="bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500 px-2 -mx-3 font-medium">
                  + {line.value}
                </div>
              );
            }
            if (line.type === 'removed') {
              return (
                <div key={idx} className="bg-red-950/40 text-red-100 border-l-2 border-red-500 px-2 -mx-3 line-through opacity-70">
                  - {line.value}
                </div>
              );
            }
            return (
              <div key={idx} className="text-gray-400 px-2 -mx-3">
                &nbsp;&nbsp;{line.value}
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
}
