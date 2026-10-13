import { describe, expect, it } from 'vitest'
import { messageOf } from './apiError'

describe('messageOf', () => {
  it('takes detail out of an API error', () => {
    expect(messageOf(new Error('409: {"detail":"Collection \\"Worm\\" already exists here"}'))).toBe('Collection "Worm" already exists here')
  })
  it('keeps other errors as they are', () => {
    expect(messageOf(new Error('Network down'))).toBe('Network down')
    expect(messageOf('boom')).toBe('boom')
  })
})
