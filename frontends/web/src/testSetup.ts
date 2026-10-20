/** jsdom не раскладывает страницу и не знает ResizeObserver: размеров в тестах нет, наблюдать нечего. */
class NoLayoutResizeObserver implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

globalThis.ResizeObserver ??= NoLayoutResizeObserver
