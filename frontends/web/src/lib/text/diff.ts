export interface DiffSegment {
  text: string
  type: 'same' | 'added' | 'removed'
}

/* ------------------------------------------------------------------ */
/*  Diff algorithm                                                    */
/* ------------------------------------------------------------------ */

export function computeDiff(original: string, updated: string): DiffSegment[] {
  // Word-level diff using longest common subsequence (LCS).
  // Split into words, find LCS, then mark words as same/added/removed.
  const oldWords = original.split(/(\s+)/) // keep whitespace as separate tokens
  const newWords = updated.split(/(\s+)/)

  // Filter to non-empty tokens for LCS, but track whitespace
  const oldTokens = oldWords.filter(w => w.length > 0)
  const newTokens = newWords.filter(w => w.length > 0)

  // Build LCS table on non-whitespace words only
  const oldW = oldTokens.filter(w => w.trim().length > 0)
  const newW = newTokens.filter(w => w.trim().length > 0)

  const m = oldW.length
  const n = newW.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = oldW[i - 1] === newW[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }

  // Backtrack to find which words are in LCS
  const oldInLcs = new Set<number>()
  const newInLcs = new Set<number>()
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (oldW[i - 1] === newW[j - 1]) {
      oldInLcs.add(i - 1)
      newInLcs.add(j - 1)
      i--; j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }

  // Build segments: walk through new words, interleave with removed old words
  const segments: DiffSegment[] = []
  let oldIdx = 0
  let newIdx = 0

  const pushSegment = (text: string, type: DiffSegment['type']) => {
    if (!text) return
    const last = segments[segments.length - 1]
    if (last && last.type === type) {
      last.text += text
    } else {
      segments.push({ text, type })
    }
  }

  while (oldIdx < oldW.length || newIdx < newW.length) {
    if (oldIdx < oldW.length && oldInLcs.has(oldIdx) && newIdx < newW.length && newInLcs.has(newIdx)) {
      // Both in LCS — same word
      pushSegment(newW[newIdx], 'same')
      oldIdx++
      newIdx++
      // Add space after if not last
      if (newIdx < newW.length) pushSegment(' ', 'same')
    } else if (oldIdx < oldW.length && !oldInLcs.has(oldIdx)) {
      // Old word not in LCS — removed
      pushSegment(oldW[oldIdx], 'removed')
      oldIdx++
      if (oldIdx < oldW.length || newIdx < newW.length) pushSegment(' ', 'removed')
    } else if (newIdx < newW.length && !newInLcs.has(newIdx)) {
      // New word not in LCS — added
      pushSegment(newW[newIdx], 'added')
      newIdx++
      if (newIdx < newW.length) pushSegment(' ', 'added')
    } else {
      break
    }
  }

  return segments
}
