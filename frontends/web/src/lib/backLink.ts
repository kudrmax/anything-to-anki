/** Куда ведёт стрелка «назад»: экран, открывший этот, кладёт путь в состояние навигации. */
export interface BackLink {
  back: string
}

export const backTo = (path: string): BackLink => ({ back: path })

export function backIn(state: unknown, fallback: string): string {
  const back: unknown = typeof state === 'object' && state !== null && 'back' in state ? state.back : null
  return typeof back === 'string' ? back : fallback
}
