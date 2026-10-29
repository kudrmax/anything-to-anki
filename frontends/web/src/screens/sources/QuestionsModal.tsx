import { useState } from 'react'
import type { Question } from '@/api/types'
import { Button, Chip, Label, Modal, Stack, Tag, Text } from '@/ui'
import css from './QuestionsModal.module.css'

interface QuestionsModalProps {
  questions: Question[]
  onCancel: () => void
  /** Ответы по вводам: у каждого ввода свои вопросы. */
  onConfirm: (answers: Record<string, string>[]) => void
}

const MODAL_TITLE = 'Add source'

const keyOf = (question: Question) => `${question.input_indexes.join(',')}:${question.id}`

/** Ответы, разложенные по вводам: у двух книг в пачке один и тот же вопрос. */
function byInput(questions: Question[], chosen: Record<string, string>): Record<string, string>[] {
  const answers: Record<string, string>[] = []
  for (const question of questions) {
    for (const index of question.input_indexes) {
      answers[index] = { ...answers[index], [question.id]: chosen[keyOf(question)] }
    }
  }
  return Array.from(answers, given => given ?? {})
}

/** Что backend спросил перед добавлением: дорожки видео, деление книги, текст или песня — для каждого файла свои. */
export function QuestionsModal({ questions, onCancel, onConfirm }: QuestionsModalProps) {
  const [answers, setAnswers] = useState<Record<string, string>>(
    () => Object.fromEntries(questions.map(question => [keyOf(question), question.default])),
  )
  const choose = (key: string, optionId: string) => setAnswers(prev => ({ ...prev, [key]: optionId }))

  return (
    <Modal
      title={MODAL_TITLE}
      onClose={onCancel}
      footer={
        <>
          <Button variant="link" onClick={onCancel}>Cancel</Button>
          <Button variant="fill" onClick={() => onConfirm(byInput(questions, answers))}>Confirm</Button>
        </>
      }
    >
      {questions.map(question => {
        const key = keyOf(question)
        const details = question.options.find(option => option.id === answers[key])?.details
        return (
          <Stack key={key} gap="m">
            <div>
              {question.input_label && <Text tone="muted" size="s">{question.input_label}</Text>}
              <Label flush>{question.prompt}</Label>
              <Stack>
                {question.options.map(option => (
                  <Chip key={option.id} outlined on={answers[key] === option.id} onClick={() => choose(key, option.id)}>
                    {option.label}
                    {option.facts.map(fact => <Tag key={fact}>{fact}</Tag>)}
                  </Chip>
                ))}
              </Stack>
            </div>
            {details && (
              <div>
                <Label flush>{details.title}</Label>
                <div className={css.details}>
                  {details.items.map((item, index) => (
                    <div key={index} className={css.item}>
                      <span>{item.text}</span>
                      {item.note && <span className={css.note}>{item.note}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Stack>
        )
      })}
    </Modal>
  )
}
