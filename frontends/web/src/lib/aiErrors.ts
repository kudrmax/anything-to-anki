const VPN_ERROR_MARKER = 'Blocked country'

/** AI-прокси отвечает этой ошибкой, когда хост вне разрешённой страны. */
export const isVpnErrorText = (text: string | null | undefined): boolean => Boolean(text?.includes(VPN_ERROR_MARKER))

export const isVpnError = (e: unknown): boolean => e instanceof Error && isVpnErrorText(e.message)
