import { Link } from 'react-router-dom'
import { useAnkiStatus } from '@/hooks/useAnkiStatus'
import css from './AnkiProblemsBanner.module.css'

/** Висит на всех экранах, пока note type в Anki не может принять карточки целиком. */
export function AnkiProblemsBanner() {
  const status = useAnkiStatus()
  const problems = status?.note_type_problems ?? []
  if (problems.length === 0) return null
  return (
    <div className={css.banner} role="alert">
      <div className={css.title}>Export to Anki is blocked: cards would lose their content</div>
      <ul className={css.list}>
        {problems.map(problem => (
          <li key={problem.note_type}>
            {problem.exists
              ? <>Note type «{problem.note_type}» lacks fields: <b>{problem.missing_fields.join(', ')}</b></>
              : <>Note type «{problem.note_type}» is not in Anki</>}
          </li>
        ))}
      </ul>
      <Link className={css.fix} to="/settings?section=anki">Fix in Settings → Anki → Create type</Link>
    </div>
  )
}
