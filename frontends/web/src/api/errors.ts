/** Ответ API с ошибкой: код и тело. Текст — «код: тело», его разбирает messageOf. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, body: string) {
    super(`${status}: ${body}`)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Ревью больше не держится на сервере (перезапуск или вытеснение): его открывают заново. */
export const REVIEW_EXPIRED_STATUS = 410

export class ReviewExpiredError extends ApiError {
  constructor(body: string) {
    super(REVIEW_EXPIRED_STATUS, body)
    this.name = 'ReviewExpiredError'
  }
}
