import { describe, expect, it } from 'vitest'
import { dragDirection, dragProgress, releasedDirection, swipeAxis } from './swipeDecision'

const SIZE = { width: 300, height: 500 }
const STILL = { vx: 0, vy: 0 }

describe('swipeAxis', () => {
  it('a small move is still a tap', () => {
    expect(swipeAxis({ dx: 5, dy: 5 })).toBeNull()
  })

  it('the larger move picks where the gesture started', () => {
    expect(swipeAxis({ dx: -20, dy: 8 })).toBe('x')
    expect(swipeAxis({ dx: 6, dy: 30 })).toBe('y')
  })
})

describe('dragDirection', () => {
  it('right is Learn side, left is Know side, down is Skip side', () => {
    expect(dragDirection({ dx: 40, dy: 0 }, true)).toBe('right')
    expect(dragDirection({ dx: -40, dy: 0 }, true)).toBe('left')
    expect(dragDirection({ dx: 0, dy: 40 }, true)).toBe('down')
  })

  it('follows where the card is now, not where the gesture started', () => {
    expect(dragDirection({ dx: -60, dy: 90 }, true)).toBe('down')
  })

  it('up decides nothing', () => {
    expect(dragDirection({ dx: 10, dy: -40 }, true)).toBeNull()
  })

  it('down decides nothing while the vertical belongs to scrolling', () => {
    expect(dragDirection({ dx: 10, dy: 40 }, false)).toBeNull()
  })
})

describe('dragProgress', () => {
  it('grows to the threshold and stops at 1', () => {
    expect(dragProgress('right', { dx: 45, dy: 0 }, SIZE)).toBeCloseTo(0.5)
    expect(dragProgress('left', { dx: -400, dy: 0 }, SIZE)).toBe(1)
    expect(dragProgress('down', { dx: 0, dy: 50 }, SIZE)).toBeCloseTo(0.5)
    expect(dragProgress(null, { dx: 0, dy: -50 }, SIZE)).toBe(0)
  })
})

describe('releasedDirection', () => {
  it('a card dragged past the threshold is decided', () => {
    expect(releasedDirection({ dx: 95, dy: 0 }, STILL, SIZE, true)).toBe('right')
    expect(releasedDirection({ dx: 0, dy: 105 }, STILL, SIZE, true)).toBe('down')
  })

  it('a card moved left, then down, flies down', () => {
    expect(releasedDirection({ dx: -70, dy: 120 }, STILL, SIZE, true)).toBe('down')
  })

  it('a card released short of the threshold comes back', () => {
    expect(releasedDirection({ dx: -60, dy: 0 }, { vx: -0.1, vy: 0 }, SIZE, true)).toBeNull()
  })

  it('a quick flick decides before the threshold', () => {
    expect(releasedDirection({ dx: -60, dy: 0 }, { vx: -0.8, vy: 0 }, SIZE, true)).toBe('left')
  })

  it('a flick back toward the start does not decide', () => {
    expect(releasedDirection({ dx: 60, dy: 0 }, { vx: -0.8, vy: 0 }, SIZE, true)).toBeNull()
  })

  it('a fast twitch shorter than a flick does not decide', () => {
    expect(releasedDirection({ dx: 20, dy: 0 }, { vx: 2, vy: 0 }, SIZE, true)).toBeNull()
  })

  it('a card pulled up comes back', () => {
    expect(releasedDirection({ dx: 0, dy: -200 }, { vx: 0, vy: -2 }, SIZE, true)).toBeNull()
  })
})
