import type { SourceStatus } from '@/api/types'

/** Что предлагает кнопка набора, который ещё не обработан или чья обработка упала. */
export const PROCESS_LABEL: Partial<Record<SourceStatus, string>> = { new: 'Process', error: 'Retry' }

/** Набор ещё не обработан или обработка упала: кнопка предлагает обработку, а не ревью. */
export const offersProcess = (status: SourceStatus): boolean => PROCESS_LABEL[status] !== undefined
