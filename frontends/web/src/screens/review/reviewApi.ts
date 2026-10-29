import { createContext, useContext } from 'react'
import { api } from '@/api/client'
import { mediaUrl } from '@/lib/text/meaning'

/** Всё, что экран ревью берёт снаружи: запросы к ревью и адреса медиа. */
export type ReviewApi = Pick<typeof api,
  | 'openReview' | 'reviewRows' | 'reviewAround' | 'setReviewSection' | 'reviewChanges' | 'reviewContents' | 'reviewText'
  | 'getReviewGeneration' | 'runReviewGeneration' | 'cancelReviewGeneration' | 'downloadReviewVideos'
  | 'previewCloze' | 'saveCloze' | 'decidePhrase' | 'undoDecision'
  | 'generateMeaning' | 'regeneratePhraseMedia' | 'generatePhraseTTS' | 'replaceWithExample' | 'replaceWithTarget' | 'changeTarget'
  | 'suggestTargetImages' | 'searchTargetImages' | 'applyTargetImage' | 'pasteTargetImage'
  | 'polishPhraseAgain' | 'setPolishReverted' | 'editPhrase' | 'setPhraseBoundary' | 'addManualCandidate'
  | 'getReportReasons' | 'reportCandidate'
> & { mediaUrl: typeof mediaUrl }

// Наследует от клиента, а не копирует его: метод берётся у клиента в момент вызова.
const BACKEND_REVIEW_API: ReviewApi = Object.assign(Object.create(api) as typeof api, { mediaUrl })

/** Откуда экран ревью берёт данные: обычно бэкенд, в редакторе раскладки — образец. Сам экран разницы не знает. */
export const ReviewApiContext = createContext<ReviewApi>(BACKEND_REVIEW_API)

export const useReviewApi = (): ReviewApi => useContext(ReviewApiContext)
