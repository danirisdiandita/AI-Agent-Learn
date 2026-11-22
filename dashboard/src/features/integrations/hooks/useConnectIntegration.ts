import { useMutation } from '@tanstack/react-query'
import { useEffect } from 'react'
import { connectIntegration } from '@/features/integrations/api'

export function useConnectIntegration() {
  const mutation = useMutation({
    mutationFn: connectIntegration,
    // The provider's consent page sends the browser back to the callback, which returns it to /integrations.
    onSuccess: (authorizationUrl) => window.location.assign(authorizationUrl),
  })
  // Going back from the provider can restore this page from the back-forward cache, still busy redirecting.
  const { reset } = mutation
  useEffect(() => {
    const onShow = (event: PageTransitionEvent) => {
      if (event.persisted) reset()
    }
    window.addEventListener('pageshow', onShow)
    return () => window.removeEventListener('pageshow', onShow)
  }, [reset])
  return mutation
}
