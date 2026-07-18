// Skill plugin renderer registry (ARC-011 P3-028).
//
// A skill plugin renders form fields (or other skill-specific UI surfaces) that
// the generic components do not understand out of the box. The registry is the
// extension point: a future skill ships a renderer, registers it, and the
// DynamicFormFields component picks it up without the form component itself
// gaining a new branch — the same "drop a directory, no UI code changes"
// guarantee the backend already provides (ARC-011 §7.14).
//
// The registry is intentionally tiny and synchronous. Plugin discovery is the
// app's responsibility (import + register at module load); the registry only
// resolves a renderer for a given field at render time. A generic fallback
// renderer (render-as-text + warning) is seeded so an unknown field type never
// breaks the form — the P3-028 "generic fallback" AC.
import type { FormField } from '../api/client';
import type { ReactNode } from 'react';

/**
 * Props passed to a skill plugin renderer. Mirrors the FieldInput contract so
 * a plugin is a drop-in replacement for the built-in field controls.
 */
export interface SkillPluginRendererProps {
  field: FormField;
  /** Current value (already resolved: row value, else default, else ''). */
  value: unknown;
  onChange: (value: unknown) => void;
}

/**
 * A renderer for one or more field types. Registered against the plugin
 * registry; the first renderer whose `canRender` returns true wins.
 */
export interface SkillPluginRenderer {
  /** Stable id for diagnostics (e.g. "rl-hpo-matrix"). */
  id: string;
  /** Whether this renderer handles the given field. */
  canRender: (field: FormField) => boolean;
  /** Render the field control. */
  render: (props: SkillPluginRendererProps) => ReactNode;
}
