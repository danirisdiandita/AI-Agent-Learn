import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './design.css'
import './tailwind.css'
import { SessionExpired } from './api/request.ts'
import { createAppRouter } from './app/router.tsx'
import { queryKeys } from './lib/queryKeys.ts'

// Dropping the session query reruns the route guards, which find no session and send the user to sign-in.
const signInAgain = (error: Error) => {
  if (!(error instanceof SessionExpired)) return
  queryClient.removeQueries({ queryKey: queryKeys.session })
  void router.invalidate()
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: signInAgain }),
  mutationCache: new MutationCache({ onError: signInAgain }),
})
const router = createAppRouter(queryClient)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
