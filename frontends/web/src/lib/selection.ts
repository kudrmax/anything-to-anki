export interface Selection {
  ids: ReadonlySet<number>
  anchor: number | null
}

export const EMPTY_SELECTION: Selection = { ids: new Set(), anchor: null }

interface Modifiers { toggle: boolean; range: boolean }

/** Выбор как в Finder: Cmd — добавить/убрать, Shift — диапазон от якоря; пока что-то выбрано, обычный клик тоже переключает. */
export function clickSelect(sel: Selection, order: number[], id: number, mods: Modifiers): Selection {
  if (mods.range && sel.anchor !== null && order.includes(sel.anchor)) {
    const [from, to] = [order.indexOf(sel.anchor), order.indexOf(id)].sort((a, b) => a - b)
    return { ids: new Set(order.slice(from, to + 1)), anchor: sel.anchor }
  }
  if (mods.toggle || sel.ids.size > 0) {
    const ids = new Set(sel.ids)
    if (ids.has(id)) ids.delete(id)
    else ids.add(id)
    return { ids, anchor: id }
  }
  return sel
}

export const selectAll = (order: number[]): Selection => ({ ids: new Set(order), anchor: order[0] ?? null })

export function pruned(sel: Selection, order: number[]): Selection {
  const visible = new Set(order)
  const ids = new Set([...sel.ids].filter(id => visible.has(id)))
  return ids.size === sel.ids.size ? sel : { ids, anchor: sel.anchor !== null && visible.has(sel.anchor) ? sel.anchor : null }
}
