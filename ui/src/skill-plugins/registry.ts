// Skill plugin renderer registry (ARC-011 P3-028).
//
// Resolution order: the first registered renderer whose `canRender(field)`
// returns true wins. If none match, `resolve()` returns `null` and the caller
// falls back to its built-in text input + warning (the P3-028 generic
// fallback, which lives in DynamicFormFields so it stays co-located with the
// form's other field controls).
//
// The registry is a module-level singleton. Apps register plugins at import
// time (e.g. from a barrel in `skill-plugins/index.ts`); tests can `reset()`
// between cases.
import type { FormField } from '../api/client';
import type { SkillPluginRenderer } from './types';

const _renderers: SkillPluginRenderer[] = [];

/**
 * Register a skill plugin renderer. Idempotent on `renderer.id` — re-registering
 * the same id replaces the prior entry (hot-reload friendly).
 */
export function register(renderer: SkillPluginRenderer): () => void {
  const existing = _renderers.findIndex((r) => r.id === renderer.id);
  if (existing >= 0) {
    _renderers[existing] = renderer;
  } else {
    _renderers.push(renderer);
  }
  return () => unregister(renderer.id);
}

/** Remove a renderer by id. */
export function unregister(id: string): void {
  const idx = _renderers.findIndex((r) => r.id === id);
  if (idx >= 0) _renderers.splice(idx, 1);
}

/**
 * Resolve a renderer for the given field, or `null` if no plugin handles it.
 * The generic text-fallback is the caller's responsibility (DynamicFormFields).
 */
export function resolve(field: FormField): SkillPluginRenderer | null {
  for (const renderer of _renderers) {
    if (renderer.canRender(field)) return renderer;
  }
  return null;
}

/** Test-only: clear the registry. */
export function reset(): void {
  _renderers.length = 0;
}
