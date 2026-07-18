// Skill plugin renderer registry barrel (ARC-011 P3-028).
//
// Importing this module is the single integration point: it re-exports the
// registry API and registers the seed renderers. Today the only seed is the
// generic field fallback (which keeps unknown field types usable); future
// skills add their own `register()` calls here.
//
// Usage from the app entrypoint:
//   import './skill-plugins';   // registers seed plugins, no side effects beyond that
export { register, unregister, resolve, reset } from './registry';
export type { SkillPluginRenderer, SkillPluginRendererProps } from './types';
