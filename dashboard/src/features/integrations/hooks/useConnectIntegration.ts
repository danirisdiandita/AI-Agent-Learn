import { useMutation } from '@tanstack/react-query'
import { connectIntegration } from '@/features/integrations/api'

export function useConnectIntegration() {
  return useMutation({
    mutationFn: connectIntegration,
    // The provider's consent page sends the browser back to the callback, which returns it to /integrations.
    onSuccess: (authorizationUrl) => window.location.assign(authorizationUrl),
  })
}
