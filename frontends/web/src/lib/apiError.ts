const API_ERROR = /^\d{3}: (.*)$/s

/** Текст ошибки для человека: у ответа API — его detail или detail.message. */
export function messageOf(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error)
  const body = API_ERROR.exec(text)?.[1]
  if (!body) return text
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    const message = (detail as { message?: unknown } | null)?.message
    return typeof message === 'string' ? message : text
  } catch {
    return text
  }
}
