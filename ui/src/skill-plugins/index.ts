// Skill plugin renderer registry barrel (ARC-011 P3-028).
//
// This module is a pure re-export: it surfaces the registry API
// (`register`/`unregister`/`resolve`/`reset`) and the renderer types so app
// code can import them from one place. It registers no plugins itself — the
// generic field-type fallback lives in `DynamicFormFields.tsx` (the
// `KNOWN_TYPES` switch + the yellow "unknown type" warning), not in this
// registry, so the form stays usable even with zero plugins registered.
//
// Integration: a skill that ships a custom renderer calls `register(...)` at
// module load (see `./README.md` §"How to ship a renderer"). The app
// entrypoint imports the renderer module so the `register()` side effect
// runs; this barrel is the import path for the registry primitives
// themselves.
export { register, unregister, resolve, reset } from './registry';
export type { SkillPluginRenderer, SkillPluginRendererProps } from './types';
