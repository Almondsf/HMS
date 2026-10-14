import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, restoreSession, session, SESSION_ENDED } from './api'
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
  /** True while checking for an existing session on page load. */
  loading: boolean
  login: (email: string, password: string) => Promise<CurrentUser>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(true)

  const endSession = useCallback(() => {
    session.set(null)
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  // Restore the session from the httpOnly refresh cookie (nothing is kept in browser storage)
  useEffect(() => {
    let cancelled = false
    restoreSession()
      .then((access) => (access ? api<CurrentUser>('/api/v1/auth/me/') : null))
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch(() => {
        if (!cancelled) endSession()
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [endSession])

  // The API client signals when the session can't be renewed
  useEffect(() => {
    window.addEventListener(SESSION_ENDED, endSession)
    return () => window.removeEventListener(SESSION_ENDED, endSession)
  }, [endSession])

  const login = useCallback(async (email: string, password: string) => {
    // In cookie mode the refresh token arrives as an httpOnly cookie, not in the body
    const { access } = await api<{ access: string }>('/api/v1/auth/login/', {
      method: 'POST',
      body: { email, password },
      anonymous: true,
    })
    session.set(access)
    const me = await api<CurrentUser>('/api/v1/auth/me/')
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    // Revokes the refresh token server-side and clears the cookie; sign out locally regardless
    await api('/api/v1/auth/logout/', { method: 'POST', body: {}, anonymous: true }).catch(() => undefined)
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
