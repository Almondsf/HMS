import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, SESSION_ENDED, tokenStore, type Tokens } from './api'
import type { Role } from './roles'

export interface CurrentUser {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  user_type: Role
}

interface AuthState {
  user: CurrentUser | null
  /** True while checking a stored session on page load. */
  loading: boolean
  login: (email: string, password: string) => Promise<CurrentUser>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(() => tokenStore.get() !== null)

  const endSession = useCallback(() => {
    tokenStore.clear()
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  // Restore a stored session on load
  useEffect(() => {
    if (!tokenStore.get()) return
    api<CurrentUser>('/api/v1/auth/me/')
      .then(setUser)
      .catch(endSession)
      .finally(() => setLoading(false))
  }, [endSession])

  // The API client signals when the session can't be renewed
  useEffect(() => {
    window.addEventListener(SESSION_ENDED, endSession)
    return () => window.removeEventListener(SESSION_ENDED, endSession)
  }, [endSession])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api<Tokens>('/api/v1/auth/login/', {
      method: 'POST',
      body: { email, password },
      anonymous: true,
    })
    tokenStore.set({ access: tokens.access, refresh: tokens.refresh })
    const me = await api<CurrentUser>('/api/v1/auth/me/')
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    const tokens = tokenStore.get()
    if (tokens) {
      // Revoke the refresh token server-side; sign out locally regardless
      await api('/api/v1/auth/logout/', { method: 'POST', body: { refresh: tokens.refresh } }).catch(() => undefined)
    }
    endSession()
  }, [endSession])

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}

/** The signed-in user; only call inside routes that require sign-in. */
export function useCurrentUser(): CurrentUser {
  const { user } = useAuth()
  if (!user) throw new Error('useCurrentUser called without a signed-in user')
  return user
}
