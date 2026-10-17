import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, restoreSession, session, SESSION_ENDED } from './api'
import { setMonitoringUser } from './monitoring'
import type { Role } from './roles'

export interface CurrentUser {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  user_type: Role
  must_change_password: boolean
  /** Platform site superusers: may open the operator dashboard */
  is_platform_operator?: boolean
  two_factor: TwoFactorStatus
}

export interface TwoFactorStatus {
  enabled: boolean
  /** This role must use it (platform operators and hospital admins, in production) */
  required: boolean
  recovery_codes_left: number
}

/** Must set up two-factor sign-in before using anything else. */
export function needsTwoFactorSetup(user: CurrentUser): boolean {
  return user.two_factor.required && !user.two_factor.enabled
}

/** The password was right; a code from the authenticator app comes next. */
export interface TwoFactorChallenge {
  challenge: string
}

interface AuthState {
  user: CurrentUser | null
  /** True while checking for an existing session on page load. */
  loading: boolean
  /** Signs in, or returns a challenge when a two-factor code is needed next */
  login: (email: string, password: string) => Promise<CurrentUser | TwoFactorChallenge>
  verifyTwoFactor: (challenge: string, code: string) => Promise<CurrentUser>
  /** Reload the signed-in user, e.g. after turning on two-factor sign-in */
  refreshUser: () => Promise<void>
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

  const startSession = useCallback(async (access: string) => {
    session.set(access)
    const me = await api<CurrentUser>('/api/v1/auth/me/')
    setUser(me)
    return me
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      // In cookie mode the refresh token arrives as an httpOnly cookie, not in the body
      const result = await api<{ access?: string; two_factor_required?: boolean; challenge?: string }>(
        '/api/v1/auth/login/',
        { method: 'POST', body: { email, password }, anonymous: true },
      )
      if (result.two_factor_required && result.challenge) return { challenge: result.challenge }
      return startSession(result.access!)
    },
    [startSession],
  )

  const verifyTwoFactor = useCallback(
    async (challenge: string, code: string) => {
      const { access } = await api<{ access: string }>('/api/v1/auth/login/verify/', {
        method: 'POST',
        body: { challenge, code },
        anonymous: true,
      })
      return startSession(access)
    },
    [startSession],
  )

  const refreshUser = useCallback(async () => {
    setUser(await api<CurrentUser>('/api/v1/auth/me/'))
  }, [])

  const logout = useCallback(async () => {
    // Revokes the refresh token server-side and clears the cookie; sign out locally regardless
    await api('/api/v1/auth/logout/', { method: 'POST', body: {}, anonymous: true }).catch(() => undefined)
    endSession()
  }, [endSession])

  // Error reports carry the user's internal id and role only
  useEffect(() => setMonitoringUser(user), [user])

  const value = useMemo(
    () => ({ user, loading, login, verifyTwoFactor, refreshUser, logout }),
    [user, loading, login, verifyTwoFactor, refreshUser, logout],
  )
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
