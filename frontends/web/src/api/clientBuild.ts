const CLIENT_BUILD_HEADER = 'X-Client-Build'
const STALE_CLIENT_HEADER = 'X-Client-Stale'
const BUNDLE_PATH = /\/assets\/([^/]+\.js)$/

/** Бандл, с которым открыта страница. В dev-сервере его нет — тогда сборку не сверяем. */
const build: string | null = (() => {
  const src = document.querySelector<HTMLScriptElement>('script[type="module"][src*="/assets/"]')?.src ?? ''
  return BUNDLE_PATH.exec(src)?.[1] ?? null
})()

export const buildHeaders = (): Record<string, string> => (build ? { [CLIENT_BUILD_HEADER]: build } : {})

let reloading = false

/** Сервер сообщил, что вышла новая сборка: перезагружаемся, чтобы не работать на старой. */
export function reloadIfStale(res: Response): void {
  if (!build || reloading || !res.headers.get(STALE_CLIENT_HEADER)) return
  reloading = true
  window.location.reload()
}
