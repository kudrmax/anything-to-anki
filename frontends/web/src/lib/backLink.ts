/** Куда ведёт стрелка «назад»: экран, открывший этот, кладёт путь в состояние навигации. */
export interface BackLink {
  back: string
}

export const backTo = (path: string): BackLink => ({ back: path })

/** Путь «назад» из состояния навигации; без него — fallback (undefined — стрелки нет). */
export function backIn<Fallback extends string | undefined>(state: unknown, fallback: Fallback): string | Fallback {
  const back: unknown = typeof state === 'object' && state !== null && 'back' in state ? state.back : null
  return typeof back === 'string' ? back : fallback
}
