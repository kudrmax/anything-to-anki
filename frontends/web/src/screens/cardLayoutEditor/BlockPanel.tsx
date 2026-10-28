import type { ReactNode } from 'react'
import type { CardLayoutEdit, CardLayoutView } from '@/api/types'
import { kindOf, styleOf } from '@/cardLayout'
import { Button, Segmented, Switch } from '@/ui'
import { ALIGN_OPTIONS, ELEMENT_HINT, ELEMENT_LABEL, SIZE_OPTIONS, SPACE_OPTIONS, SPACE_SIDES, STICKS_OPTIONS, TONE_OPTIONS, VALIGN_OPTIONS } from './labels'
import type { LayoutSelection } from '@/cardLayout'
import css from './cardLayoutEditor.module.css'

interface BlockPanelProps {
  view: CardLayoutView
  selection: LayoutSelection
  edit: (change: CardLayoutEdit) => void
  /** Правка, после которой выбранного на месте больше нет. */
  editAndDeselect: (change: CardLayoutEdit) => void
}

function Option({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={css.option}>
      <span className={css.optionLabel}>{label}</span>
      {children}
    </div>
  )
}

/** Настройки выбранного на превью: стиль блока или удаление линии. */
export function BlockPanel({ view, selection, edit, editAndDeselect }: BlockPanelProps) {
  if (selection.kind === 'divider') {
    const { column, row } = selection
    const line = view.layout.columns[column]?.rows[row]
    return (
      <div className={css.panel}>
        <p className={css.panelTitle}>Divider</p>
        <p className={css.panelHint}>A line across the column.</p>
        {line?.kind === 'divider' && (
          <Option label="Sticks to">
            <Segmented value={line.sticks} options={STICKS_OPTIONS} onChange={sticks => edit({ kind: 'stick_divider', column, row, sticks })} />
          </Option>
        )}
        <div className={css.panelActions}>
          <Button variant="danger-link" onClick={() => editAndDeselect({ kind: 'remove_divider', column: selection.column, row: selection.row })}>
            Remove divider
          </Button>
        </div>
      </div>
    )
  }

  const { element } = selection
  const style = styleOf(view, element)
  const kind = kindOf(view, element)
  if (!style) return null
  const hidden = view.hidden.includes(element)
  const canHide = view.elements.find(entry => entry.element === element)?.can_hide ?? true
  return (
    <div className={css.panel}>
      <p className={css.panelTitle}>{ELEMENT_LABEL[element]}</p>
      <p className={css.panelHint}>{ELEMENT_HINT[element]}</p>
      {kind !== 'control' && (
        <Option label="Size">
          <Segmented value={style.size} options={SIZE_OPTIONS} onChange={size => edit({ kind: 'restyle_block', element, size })} />
        </Option>
      )}
      {kind === 'text' && (
        <>
          <Option label="Colour">
            <Segmented value={style.tone} options={TONE_OPTIONS} onChange={tone => edit({ kind: 'restyle_block', element, tone })} />
          </Option>
          <Option label="Bold">
            <Switch label="Bold" checked={style.bold} onChange={bold => edit({ kind: 'restyle_block', element, bold })} />
          </Option>
        </>
      )}
      <Option label="In its row">
        <Segmented value={style.align} options={ALIGN_OPTIONS} onChange={align => edit({ kind: 'restyle_block', element, align })} />
      </Option>
      <Option label="Vertically">
        <Segmented value={style.valign} options={VALIGN_OPTIONS} onChange={valign => edit({ kind: 'restyle_block', element, valign })} />
      </Option>
      <div className={css.option}>
        <span className={css.optionLabel}>Space around</span>
        <div className={css.spaceGrid}>
          {SPACE_SIDES.map(({ side, label }) => (
            <Option key={side} label={label}>
              <Segmented value={style[`space_${side}`]} options={SPACE_OPTIONS} onChange={space => edit({ kind: 'restyle_block', element, [`space_${side}`]: space })} />
            </Option>
          ))}
        </div>
      </div>
      {!hidden && canHide && (
        <div className={css.panelActions}>
          <Button variant="link" onClick={() => edit({ kind: 'hide_block', element })}>Hide block</Button>
        </div>
      )}
    </div>
  )
}
