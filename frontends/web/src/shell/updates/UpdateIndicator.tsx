import { useUpdates } from './useUpdates'
import css from './UpdateIndicator.module.css'

/** Тихая строка в шапке, пока есть релиз новее установленного; клик открывает попап обновления. */
export function UpdateIndicator() {
  const { status, openOffer } = useUpdates()
  if (!status?.available) return null
  return <button type="button" className={css.indicator} onClick={openOffer}>Update available</button>
}
