const API_ERROR = /^\d{3}: (.*)$/s

/** Текст ошибки для человека: у ответа API — его detail. */
export function messageOf(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error)
  const body = API_ERROR.exec(text)?.[1]
  if (!body) return text
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail
    return typeof detail === 'string' ? detail : text
  } catch {
    return text
  }
}
