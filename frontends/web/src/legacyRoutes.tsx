import { Navigate, useParams, useSearchParams } from 'react-router-dom'
import { exportPath, reviewPath, sourceScope } from '@/lib/scope'

const CANDIDATE_PARAM = 'candidate'

function useSourceScope() {
  return sourceScope(Number(useParams().id))
}

/** Старая закладка ревью источника: тот же набор по общему адресу ревью. */
export function OldSourceReview() {
  const scope = useSourceScope()
  const candidate = useSearchParams()[0].get(CANDIDATE_PARAM)
  return <Navigate to={reviewPath(scope, candidate === null ? undefined : Number(candidate))} replace />
}

/** Старая закладка экспорта источника: экспорт его набора. */
export function OldSourceExport() {
  return <Navigate to={exportPath(useSourceScope())} replace />
}
