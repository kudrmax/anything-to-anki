const collapse = (text: string): string => text.replace(/\s+/g, ' ')

/**
 * Слово кандидата в тексте источника. Если его выделение перекрыто другой фразой,
 * берётся любое выделенное слово из того же фрагмента.
 */
export function findMark(container: ParentNode, candidateId: number, fragment: string): HTMLElement | null {
  const own = container.querySelector<HTMLElement>(`[data-mark-id="${candidateId}"]`)
  if (own) return own
  const normalized = collapse(fragment)
  for (const mark of container.querySelectorAll<HTMLElement>('[data-mark-id]')) {
    if (mark.textContent && normalized.includes(collapse(mark.textContent))) return mark
  }
  return null
}
