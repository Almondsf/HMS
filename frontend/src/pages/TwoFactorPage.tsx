import { useNavigate } from 'react-router'

import { TwoFactorSettings } from '@/components/TwoFactorSettings'
import { PageHeader } from '@/components/ui'
import { needsTwoFactorSetup, useCurrentUser } from '@/lib/auth'

export function TwoFactorPage({ home = '/' }: { home?: string }) {
  const user = useCurrentUser()
  const navigate = useNavigate()
  // Sent here because it's required: go on to the app once it's set up
  const forced = needsTwoFactorSetup(user)

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Two-factor sign-in"
        description="A code from your phone as well as your password, so a stolen password alone can't open your account."
      />
      <TwoFactorSettings onFinished={forced ? () => navigate(home, { replace: true }) : undefined} />
    </div>
  )
}
