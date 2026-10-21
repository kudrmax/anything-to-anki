import type { TextPlace } from '@/api/types'
import { LAST_BLOCK } from './useReviewWindow'

/**
 * Высота символа незагруженного текста в панели, в пикселях: оценка для заглушки, не правило. Замерена
 * на нарисованных кусках в колонке шириной --aside (0.62 на абзац сплошного текста), с запасом на
 * отступы между блоками.
 */
export const TEXT_PX_PER_CHAR = 0.65

/**
 * Какой кусок грузить для заглушки у экрана: с края, что обращён к колонке. Заглушка, что закрывает
 * колонку целиком (прокрутили в середину незагруженного), — кусок под серединой колонки: место символа
 * обратно высоте заглушки.
 */
export function gapPlace(
  gap: { start: number; end: number | null; startOffset: number },
  rect: { top: number; bottom: number },
  view: { top: number; bottom: number },
): TextPlace {
  if (rect.top < view.top && rect.bottom > view.bottom) {
    const middle = (view.top + view.bottom) / 2
    return { at: gap.startOffset + Math.max(0, Math.round((middle - rect.top) / TEXT_PX_PER_CHAR)) }
  }
  if (rect.top < view.top) return { block: gap.end === null ? LAST_BLOCK : gap.end - 1 }
  return { block: gap.start }
}
