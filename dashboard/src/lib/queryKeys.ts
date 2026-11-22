// Every TanStack Query key in the dashboard. Add a key here before you use it in a hook.
export const queryKeys = {
  session: ['session'] as const,
  integrations: ['integrations'] as const,
  chatSessions: ['chat-sessions'] as const,
  chatSession: (id: number) => ['chat-sessions', id] as const,
}
