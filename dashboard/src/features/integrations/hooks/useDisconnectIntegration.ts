import { useMutation, useQueryClient } from '@tanstack/react-query'
import { disconnectIntegration } from '@/features/integrations/api'
import { queryKeys } from '@/lib/queryKeys'

export function useDisconnectIntegration() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: disconnectIntegration,
    // Returning the refetch keeps the button busy until the card shows the new state.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.integrations }),
  })
}
