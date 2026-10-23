/** Что-то указало на идущую долгую операцию: запись получила 423 или операция запущена. */
const target = new EventTarget()
const STARTED = 'long-operation'
const FINISHED = 'long-operation-finished'

/** Каждая запись, отклонённая на время долгой операции, отвечает этим кодом. */
export const LONG_OPERATION_STATUS = 423

export function notifyLongOperation(): void {
  target.dispatchEvent(new Event(STARTED))
}

export function onLongOperation(listener: () => void): () => void {
  target.addEventListener(STARTED, listener)
  return () => target.removeEventListener(STARTED, listener)
}

/** Операция над источниками закончилась, успешно или отменой: экранам пора перечитать данные. */
export function notifyLongOperationFinished(): void {
  target.dispatchEvent(new Event(FINISHED))
}

export function onLongOperationFinished(listener: () => void): () => void {
  target.addEventListener(FINISHED, listener)
  return () => target.removeEventListener(FINISHED, listener)
}

/** Ответ запуска долгой операции: оверлей узнаёт о ней сразу. */
export function startsLongOperation<T>(started: Promise<T>): Promise<T> {
  return started.then(result => {
    notifyLongOperation()
    return result
  })
}
