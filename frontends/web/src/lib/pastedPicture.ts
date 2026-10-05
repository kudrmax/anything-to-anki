const OVERLAY = '[role="dialog"], [role="menu"]'
const EDITABLE = 'input, textarea, select, [contenteditable="true"]'
const PICTURE_TYPE_PREFIX = 'image/'

interface PasteLike {
  clipboardData: DataTransfer | null
  target: EventTarget | null
}

/** Картинка из буфера, если вставка не адресована полю ввода или открытому окну. */
export function pastedPicture(e: PasteLike): File | null {
  if (document.querySelector(OVERLAY)) return null
  if (e.target instanceof Element && e.target.closest(EDITABLE)) return null
  const files = Array.from(e.clipboardData?.files ?? [])
  return files.find(file => file.type.startsWith(PICTURE_TYPE_PREFIX)) ?? null
}
