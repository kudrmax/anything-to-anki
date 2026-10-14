// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import type { CandidateSection } from '@/api/types'

export type SourceKind = 'book' | 'series' | 'song' | 'text'
export type CardStatus = 'pending' | 'learn' | 'known' | 'skip'
export type TakeOrder = 'useful' | 'text' | 'key'
export const WHOLE = 'whole'
export type Scope = string

export interface Sentence {
  id: string
  partId: string
  text: string
  /** Surface form of the target inside the text. */
  target: string
  lemma: string
  meaning: string
  /** Polish (and the rest of AI) is ready for this phrase. */
  polished: boolean
  useful: number
  key: number
}

export interface Part {
  id: string
  label: string
  title: string
  sentences: Sentence[]
}

export interface Card {
  id: string
  lemma: string
  partId: string
  sentenceId: string
  section: CandidateSection
  status: CardStatus
}

export interface Source {
  id: string
  title: string
  kind: SourceKind
  hasHeadings: boolean
  wholeLabel: string
  partNoun: string
  parts: Part[]
  cards: Card[]
}

type BankEntry = [lemma: string, meaning: string, first: string, second: string]

const FANTASY: BankEntry[] = [
  ['reluctant', 'Unwilling and hesitant', 'He was [reluctant] to open the letter in front of everyone.', 'She gave a [reluctant] nod and followed them inside.'],
  ['peculiar', 'Strange or unusual', 'There was something [peculiar] about the way the cat watched the street.', 'The shop sold the most [peculiar] things he had ever seen.'],
  ['mutter', 'To speak quietly and unclearly', 'His uncle began to [mutter] about people who wore cloaks.', 'They could hear him [mutter] under his breath all the way home.'],
  ['glimpse', 'A quick, incomplete look', 'He caught a [glimpse] of green light behind the curtain.', 'Only a [glimpse] of the castle was visible through the fog.'],
  ['grumble', 'To complain in a low voice', 'The old man would [grumble] about the weather every morning.', 'Nobody listened when he started to [grumble] again.'],
  ['astonished', 'Very surprised', 'The boy looked [astonished] when the door opened by itself.', 'She was too [astonished] to say anything at all.'],
  ['give in', 'To stop resisting', 'He refused to [give in] even when the letters kept coming.', 'In the end they had to [give in] and let him go.'],
  ['set off', 'To start a journey', 'They [set off] before the sun had risen.', 'The next morning the whole family [set off] for the coast.'],
  ['scramble', 'To move quickly and awkwardly', 'He had to [scramble] over the wall to reach the garden.', 'Everyone began to [scramble] for the door at once.'],
  ['ominous', 'Suggesting that something bad will happen', 'An [ominous] silence filled the corridor.', 'The clouds looked [ominous] as they gathered over the hills.'],
  ['bewildered', 'Confused and unable to understand', 'He stood there, [bewildered], holding the strange key.', 'The [bewildered] guard did not know whom to believe.'],
  ['rummage', 'To search untidily through things', 'She began to [rummage] through the drawers for a candle.', 'He had to [rummage] in his bag for the ticket.'],
  ['make a fuss', 'To complain or get excited about something small', 'His aunt would always [make a fuss] about the smallest scratch.', 'Please don’t [make a fuss] — it’s only a birthday.'],
  ['flinch', 'To make a sudden small movement from pain or fear', 'He didn’t even [flinch] when the door slammed.', 'She saw him [flinch] at the sound of the name.'],
  ['tremendous', 'Very great in amount or level', 'There was a [tremendous] crash from the kitchen.', 'It took a [tremendous] effort to stay awake.'],
  ['look forward to', 'To feel happy about something that is going to happen', 'He had never [looked forward to] a birthday so much.', 'She [looked forward to] the long summer evenings.'],
  ['dwindle', 'To become gradually smaller', 'Their supplies began to [dwindle] after the third day.', 'The crowd started to [dwindle] as the rain came.'],
  ['nudge', 'To push gently with the elbow', 'His friend gave him a [nudge] and pointed at the door.', 'She had to [nudge] him awake twice during the lesson.'],
  ['sheepish', 'Embarrassed because of a mistake', 'He gave a [sheepish] grin and handed back the book.', 'The twins looked [sheepish] when they were caught.'],
  ['run out of', 'To use all of something', 'They [ran out of] candles long before midnight.', 'We’re about to [run out of] time.'],
  ['stumble', 'To trip while walking', 'He would [stumble] over the loose stones in the dark.', 'She tried not to [stumble] on the narrow stairs.'],
  ['wary', 'Careful because of possible danger', 'The goblin gave them a [wary] look.', 'He had learned to be [wary] of strangers who smiled too much.'],
  ['take after', 'To look or behave like an older relative', 'Everyone said he [took after] his father.', 'Does she [take after] her mother at all?'],
  ['squint', 'To look with eyes partly closed', 'He had to [squint] to read the tiny writing.', 'The sun made them [squint] as they crossed the field.'],
  ['dreadful', 'Very bad or unpleasant', 'It had been a [dreadful] summer so far.', 'What a [dreadful] noise that thing makes!'],
  ['come across', 'To find by chance', 'He [came across] an old map in the attic.', 'You rarely [come across] a door like that.'],
  ['linger', 'To stay longer than necessary', 'The smell of smoke would [linger] for days.', 'They did not [linger] in the dark corridor.'],
  ['brisk', 'Quick and energetic', 'She walked at a [brisk] pace towards the station.', 'A [brisk] wind blew in from the lake.'],
  ['make up one’s mind', 'To decide', 'He couldn’t [make up his mind] which door to try.', 'Once she [made up her mind], nothing could stop her.'],
  ['gloomy', 'Dark and sad', 'The hall was [gloomy] and cold.', 'He felt [gloomy] for the rest of the week.'],
  ['conceal', 'To hide something', 'He tried to [conceal] the letter under his jumper.', 'There was no way to [conceal] the broken window.'],
  ['fidget', 'To move restlessly', 'The boy began to [fidget] in his seat.', 'Stop [fidget]ing and listen to me.'],
  ['put up with', 'To tolerate', 'He had to [put up with] his cousin all summer.', 'I can’t [put up with] this noise any longer.'],
  ['vanish', 'To disappear suddenly', 'The old woman seemed to [vanish] into thin air.', 'By morning the footprints had begun to [vanish].'],
  ['eerie', 'Strange and frightening', 'An [eerie] light glowed at the end of the tunnel.', 'The forest was [eerie] after dark.'],
  ['shrug off', 'To treat as unimportant', 'He tried to [shrug off] the warning.', 'She [shrugged off] the pain and kept walking.'],
  ['blurt out', 'To say something suddenly without thinking', 'He [blurted out] the answer before anyone could stop him.', 'Don’t [blurt out] the secret this time.'],
  ['cautious', 'Careful to avoid risk', 'They were [cautious] as they opened the trapdoor.', 'Be [cautious] with that wand.'],
  ['sneer', 'A smile that shows no respect', 'The boy answered with a [sneer].', 'He couldn’t hide the [sneer] on his face.'],
  ['wander off', 'To leave a place without telling anyone', 'Don’t [wander off] in the market.', 'The dog would [wander off] whenever the gate was open.'],
]

const TALK: BankEntry[] = [
  ['hang out', 'To spend time relaxing with someone', 'We should totally [hang out] this weekend.', 'They usually [hang out] at the coffee place downstairs.'],
  ['freak out', 'To become very upset or scared', 'Don’t [freak out], it’s just a haircut.', 'He’s going to [freak out] when he sees the apartment.'],
  ['awkward', 'Uncomfortable or embarrassing', 'That was the most [awkward] dinner ever.', 'It’s a little [awkward] to call her now.'],
  ['break up', 'To end a romantic relationship', 'I can’t believe they’re going to [break up].', 'Did you two [break up] again?'],
  ['make a point', 'To show an opinion clearly', 'He always has to [make a point] about everything.', 'I’m just trying to [make a point] here.'],
  ['figure out', 'To understand or solve', 'I can’t [figure out] how this thing works.', 'We’ll [figure out] the rent later.'],
  ['get over', 'To recover from something', 'You’ll [get over] her, I promise.', 'It took him months to [get over] the job.'],
  ['blunt', 'Saying exactly what you think', 'Sorry to be [blunt], but that sweater is ugly.', 'She can be pretty [blunt] sometimes.'],
  ['show up', 'To arrive somewhere', 'He didn’t even [show up] to his own party.', 'Just [show up] at eight and bring snacks.'],
  ['grossed out', 'Disgusted', 'I’m kind of [grossed out] right now.', 'She was totally [grossed out] by the fridge.'],
  ['pull off', 'To succeed in doing something difficult', 'There’s no way we can [pull off] a surprise party.', 'Only you could [pull off] that hat.'],
  ['nag', 'To keep complaining to someone', 'Stop [nag]ging me about the dishes.', 'My mom used to [nag] me about everything.'],
  ['turn down', 'To refuse an offer', 'Why would you [turn down] a free trip?', 'She had to [turn down] the job.'],
  ['clumsy', 'Moving awkwardly and dropping things', 'I’m so [clumsy] today, sorry about the coffee.', 'He’s the most [clumsy] guy I know.'],
  ['run into', 'To meet by chance', 'Guess who I [ran into] at the store?', 'I hope we don’t [run into] her ex.'],
  ['brag', 'To talk proudly about yourself', 'He won’t stop [brag]ging about his new car.', 'I don’t mean to [brag], but I was great.'],
  ['mess up', 'To do something badly', 'I totally [messed up] the interview.', 'Don’t [mess up] the furniture.'],
  ['crash at', 'To sleep at someone’s place', 'Can I [crash at] your place tonight?', 'He’s been [crash]ing at Joey’s for a week.'],
  ['pick up on', 'To notice something', 'Did you [pick up on] that look?', 'She didn’t [pick up on] the hint at all.'],
  ['bummed', 'Disappointed', 'I’m really [bummed] about the concert.', 'He was [bummed] he couldn’t come.'],
]

const LYRICS: BankEntry[] = [
  ['drift away', 'To slowly move away', 'Let the evening [drift away] on the tide.', 'I watch the lanterns [drift away].'],
  ['restless', 'Unable to stay still or calm', 'A [restless] heart keeps beating through the night.', 'The [restless] city never sleeps.'],
  ['linger', 'To stay longer than necessary', 'Your voice will [linger] in the hall.', 'Shadows [linger] by the door.'],
  ['fade', 'To slowly disappear', 'Watch the colours [fade] to grey.', 'The music starts to [fade].'],
  ['weary', 'Very tired', 'A [weary] traveller sings alone.', 'My [weary] eyes still search the sky.'],
  ['tremble', 'To shake slightly', 'The candles [tremble] in the wind.', 'I feel the floorboards [tremble].'],
]

const BLOG: BankEntry[] = [
  ['leverage', 'To use something to maximum advantage', 'Teams [leverage] existing tools instead of building new ones.', 'You can [leverage] the cache for faster builds.'],
  ['bottleneck', 'A point where progress slows down', 'The database quickly became the main [bottleneck].', 'Finding the [bottleneck] took a whole week.'],
  ['trade-off', 'A balance between two opposing things', 'Every design decision is a [trade-off].', 'The [trade-off] here is speed for memory.'],
  ['roll out', 'To introduce gradually', 'We plan to [roll out] the feature next month.', 'They will [roll out] the change region by region.'],
  ['cumbersome', 'Slow and complicated', 'The old process was [cumbersome] and error-prone.', 'Manual deployments felt [cumbersome].'],
  ['streamline', 'To make more efficient', 'We wanted to [streamline] the onboarding flow.', 'Small scripts helped [streamline] releases.'],
  ['backlog', 'Work that has not been done yet', 'The [backlog] grew faster than we could handle.', 'Clearing the [backlog] took two sprints.'],
  ['come up with', 'To think of an idea', 'We had to [come up with] a better plan.', 'Can you [come up with] a simpler name?'],
  ['robust', 'Strong and reliable', 'The new pipeline is far more [robust].', 'We need a [robust] way to handle retries.'],
  ['tweak', 'A small change', 'A tiny [tweak] in the config fixed it.', 'After one more [tweak] the tests passed.'],
  ['phase out', 'To stop using gradually', 'We will [phase out] the legacy API.', 'They decided to [phase out] the old dashboard.'],
  ['granular', 'Detailed, broken into small parts', 'We needed more [granular] permissions.', 'The logs became much more [granular].'],
]

const FILLER_FRAMES = [
  'Nobody in the room could quite explain the [w].',
  'The old [w] was still lying on the table.',
  'She had never heard anyone mention a [w] before.',
  'It was the third [w] they had seen that week.',
  'He wrote the word [w] on the back of his hand.',
  'Somewhere behind the house a [w] was waiting.',
]
const SYLLABLES = ['bra', 'lo', 'min', 'ter', 'qua', 'vel', 'dor', 'sen', 'fi', 'ral', 'tho', 'gan', 'pe', 'rix', 'mo', 'lun']

const hash = (text: string): number => {
  let h = 7
  for (const char of text) h = (h * 31 + char.charCodeAt(0)) % 100003
  return h
}

const pseudoWord = (seed: number): string => {
  const n = SYLLABLES.length
  const parts = [SYLLABLES[seed % n], SYLLABLES[Math.floor(seed / n) % n]]
  if (Math.floor(seed / (n * n)) % 2 === 0) parts.push(SYLLABLES[Math.floor(seed / (n * n * 2)) % n])
  return parts.join('')
}

const BRACKETED = /\[([^\]]+)\]/

function sentence(partId: string, index: number, raw: string, lemma: string, meaning: string, useful: number): Sentence {
  const match = BRACKETED.exec(raw)
  const target = match ? match[1] : lemma
  return {
    id: `${partId}-s${index}`,
    partId,
    text: raw.replace(BRACKETED, '$1'),
    target,
    lemma,
    meaning,
    polished: false,
    useful,
    key: hash(`${lemma}-key`) % 100,
  }
}

const REPEATED_PER_PART = 12
const BANK_USEFULNESS = 1000
const FILLER_USEFULNESS = 100

/** Text of a part: every bank word once, a dozen of them twice, then rarer filler words. */
export function buildSentences(partId: string, partIndex: number, bank: BankEntry[], size: number): Sentence[] {
  const sentences: Sentence[] = []
  const offset = (partIndex * 7) % bank.length
  const ordered = bank.map((_, k) => bank[(offset + k) % bank.length])
  ordered.forEach(([lemma, meaning, first, second], k) => {
    sentences.push(sentence(partId, sentences.length, (partIndex + k) % 2 === 0 ? first : second, lemma, meaning, BANK_USEFULNESS - hash(lemma) % 500))
  })
  ordered.slice(0, Math.min(REPEATED_PER_PART, ordered.length - 1)).forEach(([lemma, meaning, first, second], k) => {
    sentences.push(sentence(partId, sentences.length, (partIndex + k) % 2 === 0 ? second : first, lemma, meaning, BANK_USEFULNESS - hash(lemma) % 500))
  })
  for (let k = sentences.length; k < size; k++) {
    const seed = hash(`${partId}-${k}`) + k
    const word = pseudoWord(seed)
    const frame = FILLER_FRAMES[seed % FILLER_FRAMES.length]
    sentences.push(sentence(partId, k, frame.replace('[w]', `[${word}]`), word, `Mock word — a rarer word from ${partId}`, FILLER_USEFULNESS - seed % FILLER_USEFULNESS))
  }
  return sentences
}

const WORD = /[A-Za-z’']+/g
const MIN_TARGET_LENGTH = 6

/** A pasted part: each sentence becomes a phrase, its longest word the target. */
export function sentencesFromText(partId: string, text: string): Sentence[] {
  return text.split(/(?<=[.!?])\s+/).map(raw => raw.trim()).filter(Boolean).flatMap((raw, index) => {
    const words = raw.match(WORD) ?? []
    const longest = words.reduce((best, word) => (word.length > best.length ? word : best), '')
    if (longest.length < MIN_TARGET_LENGTH) return []
    return [sentence(partId, index, raw.replace(longest, `[${longest}]`), longest.toLowerCase(), `Mock meaning of “${longest.toLowerCase()}”`, BANK_USEFULNESS - index)]
  })
}

function section(lemma: string): CandidateSection {
  const bucket = hash(`${lemma}-section`) % 10
  return bucket < 7 ? 'ready' : bucket < 9 ? 'extra' : 'probably_known'
}

export const newCard = (sourceId: string, seq: number, s: Sentence): Card => ({
  id: `${sourceId}-c${seq}`,
  lemma: s.lemma,
  partId: s.partId,
  sentenceId: s.id,
  section: section(s.lemma),
  status: 'pending',
})

interface PartSeed {
  label: string
  title: string
  size: number
  taken?: number
  decided?: number
  polished?: boolean
}

function buildSource(id: string, title: string, kind: SourceKind, hasHeadings: boolean, partNoun: string, wholeLabel: string, bank: BankEntry[], seeds: PartSeed[]): Source {
  const parts = seeds.map((seed, index) => ({
    id: `${id}-p${index + 1}`,
    label: seed.label,
    title: seed.title,
    sentences: buildSentences(`${id}-p${index + 1}`, index, bank, seed.size),
  }))
  const cards: Card[] = []
  seeds.forEach((seed, index) => {
    const part = parts[index]
    const seen = new Set<string>()
    const firsts = part.sentences.filter(s => !seen.has(s.lemma) && seen.add(s.lemma))
    const taken = firsts.slice(0, seed.taken ?? 0)
    let decided = seed.decided ?? 0
    for (const s of taken) {
      if (seed.polished) s.polished = true
      const card = newCard(id, cards.length, s)
      if (card.section === 'ready' && decided > 0) {
        card.status = decided % 4 === 0 ? 'known' : 'learn'
        decided--
      }
      cards.push(card)
    }
  })
  return { id, title, kind, hasHeadings, partNoun, wholeLabel, parts, cards }
}

const CHAPTER_TITLES = [
  'The quiet street', 'The vanishing glass', 'Letters from no one', 'The keeper of the keys', 'The alley',
  'The journey', 'The sorting', 'The potions master', 'The midnight duel', 'Halloween', 'The match',
  'The mirror', 'Nicolas', 'Norbert', 'The forbidden forest', 'Through the trapdoor', 'The man with two faces',
]
const HOBBIT_TITLES = ['An unexpected party', 'Roast mutton', 'A short rest', 'Over hill and under hill', 'Riddles in the dark', 'Out of the frying-pan']

const CHAPTER_SIZE = 90
const SMALL_PART = 40

export function initialSources(): Source[] {
  return [
    buildSource('hp', 'Harry Potter', 'book', true, 'Ch', 'Whole book', FANTASY,
      CHAPTER_TITLES.map((title, i) => ({
        label: `Ch ${i + 1}`,
        title,
        size: CHAPTER_SIZE + (i * 13) % 30,
        taken: [40, 36, 58][i] ?? 0,
        decided: [20, 12, 22][i] ?? 0,
        polished: i < 2,
      }))),
    buildSource('friends', 'Friends S1', 'series', true, 'Episode', 'Whole season', TALK,
      [1, 2, 3, 4].map(n => ({ label: `Ep ${n}`, title: `Episode ${n}`, size: SMALL_PART, taken: n === 1 ? 20 : n === 2 ? 12 : 0, decided: n === 1 ? 14 : 3, polished: n === 1 }))),
    buildSource('song', 'Bohemian Rhapsody', 'song', false, 'Part', 'Whole song', LYRICS,
      [{ label: 'Song', title: 'Lyrics', size: LYRICS.length, taken: LYRICS.length, decided: 3, polished: true }]),
    buildSource('hobbit', 'The Hobbit', 'book', true, 'Ch', 'Whole book', FANTASY,
      HOBBIT_TITLES.map((title, i) => ({ label: `Ch ${i + 1}`, title, size: CHAPTER_SIZE + i * 9 }))),
    buildSource('blog', 'Long blog post', 'text', false, 'Part', 'Whole text', BLOG,
      [{ label: 'Text', title: 'Text', size: 160, taken: 18, decided: 6, polished: true }]),
  ]
}

export const BANK_FOR_KIND: Record<SourceKind, BankEntry[]> = { book: FANTASY, series: TALK, song: LYRICS, text: BLOG }
