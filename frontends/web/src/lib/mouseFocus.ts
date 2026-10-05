/**
 * Кнопка, нажатая мышью, не забирает фокус. Тогда кнопка в фокусе — всегда пришедшая с клавиатуры (Tab),
 * и Enter на ней означает нажатие именно её (Chromium считает `:focus-visible` и после клика, на него опираться нельзя).
 */
export function keepFocusOnMouseDown(e: { preventDefault: () => void }): void {
  e.preventDefault()
}
