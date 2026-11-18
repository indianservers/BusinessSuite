import { useCallback, useReducer } from "react";
import type { WorkflowDocument } from "./types";
type State = {
  past: WorkflowDocument[];
  present: WorkflowDocument;
  future: WorkflowDocument[];
};
type Action =
  | {
      type: "change";
      value:
        | WorkflowDocument
        | ((current: WorkflowDocument) => WorkflowDocument);
      history: boolean;
    }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "checkpoint" };
function reducer(state: State, action: Action): State {
  if (action.type === "undo")
    return state.past.length
      ? {
          past: state.past.slice(0, -1),
          present: state.past[state.past.length - 1],
          future: [state.present, ...state.future].slice(0, 80),
        }
      : state;
  if (action.type === "redo")
    return state.future.length
      ? {
          past: [...state.past, state.present].slice(-80),
          present: state.future[0],
          future: state.future.slice(1),
        }
      : state;
  if (action.type === "checkpoint")
    return {
      ...state,
      past: [...state.past, state.present].slice(-80),
      future: [],
    };
  const next =
    typeof action.value === "function"
      ? action.value(state.present)
      : action.value;
  return next === state.present
    ? state
    : {
        past: action.history
          ? [...state.past, state.present].slice(-80)
          : state.past,
        present: next,
        future: action.history ? [] : state.future,
      };
}
export function useDocument(initial: WorkflowDocument) {
  const [state, dispatch] = useReducer(reducer, {
    past: [],
    present: initial,
    future: [],
  });
  const update = useCallback(
    (
      value:
        | WorkflowDocument
        | ((current: WorkflowDocument) => WorkflowDocument),
      history = true,
    ) => dispatch({ type: "change", value, history }),
    [],
  );
  const undo = useCallback(() => dispatch({ type: "undo" }), []),
    redo = useCallback(() => dispatch({ type: "redo" }), []),
    checkpoint = useCallback(() => dispatch({ type: "checkpoint" }), []);
  return {
    document: state.present,
    update,
    undo,
    redo,
    checkpoint,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
  };
}
