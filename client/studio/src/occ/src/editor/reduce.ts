// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/editor/reduce.ts @ 9242a95. See src/occ/NOTICE.md.
// Pure reducer layer: the per-timeline reducer (`reduce`) + the project reducer
// (`projectReduce`, routing per-timeline actions to the active timeline) + the
// undo/redo history wrapper. The command set + React hook live in store.ts.
export type {
  Action,
  ProjectAction,
  AtomicAction,
  BatchAction,
  AnyAction,
  HistoryControlAction,
  Dispatch,
  ProjectDispatch,
} from './reducerActions';
export { isHistoryControlAction } from './reducerActions';
export type { OverwriteLaneAction } from './reducerTimelineHelpers';
export { contiguousFollowers } from './reducerTimelineHelpers';
export { applyOverwriteLaneAction } from './reducerOverwrite';
export { reduce } from './reducerTimeline';
export { maxOrder, projectReduce } from './reducerProject';
export type { History } from './reducerHistory';
export { historyReduce } from './reducerHistory';
