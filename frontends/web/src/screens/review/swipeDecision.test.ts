import { describe, expect, it } from 'vitest'
import { dragDirection, dragProgress, releasedDirection, swipeAxis } from './swipeDecision'

const SIZE = { width: 300, height: 500 }

describe('swipeAxis', () => {
  it('a small move is still a tap', () => {
    expect(swipeAxis(5, 5)).toBeNull()
  })

  it('the larger move picks the axis', () => {
    expect(swipeAxis(-20, 8)).toBe('x')
    expect(swipeAxis(6, 30)).toBe('y')
  })
})

describe('dragDirection', () => {
  it('right is Learn side, left is Know side, down is Skip side', () => {
    expect(dragDirection('x', { dx: 40, dy: 0 })).toBe('right')
    expect(dragDirection('x', { dx: -40, dy: 0 })).toBe('left')
    expect(dragDirection('y', { dx: 0, dy: 40 })).toBe('down')
  })

  it('up decides nothing', () => {
    expect(dragDirection('y', { dx: 0, dy: -40 })).toBeNull()
  })
})

describe('dragProgress', () => {
  it('grows to the threshold and stops at 1', () => {
    expect(dragProgress('x', { dx: 45, dy: 0 }, SIZE)).toBeCloseTo(0.5)
    expect(dragProgress('x', { dx: -400, dy: 0 }, SIZE)).toBe(1)
    expect(dragProgress('y', { dx: 0, dy: 50 }, SIZE)).toBeCloseTo(0.5)
    expect(dragProgress('y', { dx: 0, dy: -50 }, SIZE)).toBe(0)
  })
})

describe('releasedDirection', () => {
  it('a card dragged past the threshold is decided', () => {
    expect(releasedDirection('x', { dx: 95, dy: 0, speed: 0 }, SIZE)).toBe('right')
    expect(releasedDirection('y', { dx: 0, dy: 105, speed: 0 }, SIZE)).toBe('down')
  })

  it('a card released short of the threshold comes back', () => {
    expect(releasedDirection('x', { dx: -60, dy: 0, speed: 0.1 }, SIZE)).toBeNull()
  })

  it('a quick flick decides before the threshold', () => {
    expect(releasedDirection('x', { dx: -60, dy: 0, speed: 0.8 }, SIZE)).toBe('left')
  })

  it('a fast twitch shorter than a flick does not decide', () => {
    expect(releasedDirection('x', { dx: 20, dy: 0, speed: 2 }, SIZE)).toBeNull()
  })

  it('pulling up decides nothing', () => {
    expect(releasedDirection('y', { dx: 0, dy: -200, speed: 2 }, SIZE)).toBeNull()
  })
})
