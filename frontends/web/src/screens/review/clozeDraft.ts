import type { ClozeDraft, ClozePreview, SaveClozeRequest } from '@/api/types'

/** Черновик уходит на сохранение вместе с фразой, в которой выбраны слова. */
export function clozeSaveRequest(draft: ClozeDraft, preview: ClozePreview): SaveClozeRequest {
  return { ...draft, phrase: preview.phrase }
}

