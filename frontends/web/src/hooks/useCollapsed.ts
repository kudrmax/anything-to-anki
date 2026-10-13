import { useCallback, useState } from 'react'

const KEY = 'sources.collapsedCollections'

const load = (): Set<number> => {
  try {
    const raw = localStorage.getItem(KEY)
    return new Set(raw ? (JSON.parse(raw) as number[]) : [])
  } catch {
    return new Set()
  }
}

const store = (ids: Set<number>) => {
  try {
    localStorage.setItem(KEY, JSON.stringify([...ids]))
  } catch {
    // свёрнутость — удобство экрана, без хранилища просто не запоминается
  }
}

export function useCollapsed() {
  const [collapsed, setCollapsed] = useState(load)
  const toggle = useCallback((id: number) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      store(next)
      return next
    })
  }, [])
  return { isCollapsed: (id: number) => collapsed.has(id), toggle }
}
