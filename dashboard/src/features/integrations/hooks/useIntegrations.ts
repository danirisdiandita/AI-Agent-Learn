import { useQuery } from '@tanstack/react-query'
import { listIntegrations } from '@/features/integrations/api'
import { queryKeys } from '@/lib/queryKeys'

export function useIntegrations() {
  return useQuery({ queryKey: queryKeys.integrations, queryFn: listIntegrations })
}
