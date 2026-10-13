import { useState } from 'react'
import type { Question } from '@/api/types'
import { Button, Chip, Label, Modal, Stack } from '@/ui'
import css from './QuestionsModal.module.css'

interface QuestionsModalProps {
  questions: Question[]
  onCancel: () => void
  onConfirm: (answers: Record<string, string>) => void
}

const MODAL_TITLE = 'Add source'

/** Что backend спросил перед добавлением источника: дорожки видео, деление книги, текст или песня. */
export function QuestionsModal({ questions, onCancel, onConfirm }: QuestionsModalProps) {
  const [answers, setAnswers] = useState<Record<string, string>>(
    () => Object.fromEntries(questions.map(question => [question.id, question.default])),
  )
  const choose = (questionId: string, optionId: string) => setAnswers(prev => ({ ...prev, [questionId]: optionId }))

  return (
    <Modal
      title={MODAL_TITLE}
      onClose={onCancel}
      footer={
        <>
          <Button variant="link" onClick={onCancel}>Cancel</Button>
          <Button variant="fill" onClick={() => onConfirm(answers)}>Confirm</Button>
        </>
      }
    >
      {questions.map(question => {
        const details = question.options.find(option => option.id === answers[question.id])?.details
        return (
          <Stack key={question.id} gap="m">
            <div>
              <Label flush>{question.prompt}</Label>
              <Stack>
                {question.options.map(option => (
                  <Chip key={option.id} outlined on={answers[question.id] === option.id} onClick={() => choose(question.id, option.id)}>
                    {option.label}
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
