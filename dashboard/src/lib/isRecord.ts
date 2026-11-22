/** Narrows a parsed JSON value to an object, so its fields can be checked one by one. */
export const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null
