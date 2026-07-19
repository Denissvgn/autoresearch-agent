// Skill picker — selects a research skill from GET /skills (ARC-011 P3-021).
// Replaces the hardcoded model-type selector with a generic, descriptor-driven
// picker. Falls back to the legacy /models endpoint for backward compat.
import type { SkillSummary } from '../api/client';

interface Props {
  skills: SkillSummary[];
  selected: string | null;
  onSelect: (skillId: string) => void;
}

const CATEGORY_ICONS: Record<string, string> = {
  optimization: 'arrU',
  generative: 'flask',
  exploratory: 'search',
};

export default function SkillPicker({ skills, selected, onSelect }: Props) {
  if (skills.length === 0) {
    return (
      <div className="text-gray-500 text-sm py-4 text-center">
        No skills installed. Drop a directory under skills/ and reload.
      </div>
    );
  }

  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
      {skills.map((skill) => {
        const isSelected = skill.id === selected;
        const icon = CATEGORY_ICONS[skill.category] || 'flask';
        return (
          <button
            key={skill.id}
            type="button"
            onClick={() => onSelect(skill.id)}
            className={`card cursor-pointer text-left transition-all ${
              isSelected
                ? 'card--raised border-indigo-500'
                : 'hover:border-gray-600'
            }`}
            style={{
              padding: 12,
              borderColor: isSelected ? 'var(--indigo, #6366f1)' : undefined,
            }}
          >
            <div className="row gap-2 items-center mb-1">
              <span className="text-lg">{icon === 'arrU' ? '↗' : icon === 'flask' ? '⚗' : '🔍'}</span>
              <span className="font-medium text-sm">{skill.display_name}</span>
            </div>
            <div className="text-xs text-gray-500">{skill.description}</div>
            <div className="mt-2 flex gap-2 text-xs text-gray-600">
              <span className="px-1.5 py-0.5 rounded bg-gray-800">{skill.category}</span>
              {skill.model_type && (
                <span className="px-1.5 py-0.5 rounded bg-gray-800 mono">{skill.model_type}</span>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
