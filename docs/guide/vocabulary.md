# Your vocabulary and level

The app suggests only words that are new to you. It decides what is new from three things: your **level**, your **known words** and how **frequent** a word is.

## Level

**Settings → Vocabulary → Target CEFR level** is your English level, from A1 to C2. The default is **B1**. Words above your level are suggested for learning; words at or below it are treated as known.

Set it before you add your first sources. Changing it later re-analyses **every** source: the app runs **Find words again** on all of them as one operation, behind the progress overlay. Your decisions are kept.

## Known words

A word becomes **known** in three ways:

- you press **Know** on one of its cards;
- you mark it during [calibration](#calibration);
- 30 days pass after you export it to Anki.

A known word is never suggested again, in any source. Known is decided per word: knowing `run` as a verb also covers `run` as a noun.

To undo it, remove the word in **Settings → Known words**. Its cards become new again everywhere.

## Learning

Words you marked **Learn** or **Cloze** are **learning**. They are not suggested as new either. **Settings → Learning** lists them:

- **In Anki**: exported, with the day each one becomes known.
- **Waiting for export**: marked, but not in Anki yet.

## Unknown words

**Unknown words** are the opposite of known words: words you told the app you don't know. You add them with the **Unknown words** button (`U`) on a card. A phrase that contains an unknown word (other than its target) never counts as **Ready**. Manage the list in **Settings → Unknown words**.

## Frequent words

Very common words are probably known to you, even above your level. **Settings → Vocabulary → Frequent words** sets how common a word must be to go to the **Probably known** section in Review. These words are moved down, not removed.

| Option | Example words at that level |
|---|---|
| **Auto** (default) | Starts from your level, then learns from your **Learn** and **Know** presses |
| 4.0 | naked, divorce, awkward, hilarious |
| 4.5 | concept, classic, assume, weird |
| 5.0 | career, issue, available, figure out |
| 5.5 | end up, find out, come in, get out |
| **Off** | Nothing goes down for being frequent |

Auto starts where a learner of your level probably knows a word: 5.5 at A1 and A2, 5.0 at B1, 4.5 at B2, 4.0 at C1 and C2. A beginner keeps everyday words of the next level on top; an advanced learner sends the common ones down. Then it moves one step at a time: down while the words just below are mostly marked **Know**, up while the words just above are mostly marked **Learn**. A step needs at least four marked words to move.

The numbers are [Zipf frequencies](https://github.com/rspeer/wordfreq#usage): 6 is a very common word, 3 is a rare one. Changing this setting re-analyses every source, like a level change.

## Calibration

A new user knows thousands of words above their level that the app doesn't know about. Calibration lets you mark many of them as known quickly.

1. Open **Settings → Vocabulary → Vocabulary calibration** and press **Prepare**. The app builds a word list from the dictionaries; this takes a moment.
2. Press **Calibrate**.
3. Each round shows up to 15 words from the three levels above yours. Tap every word you know, then press **Next N words**.
4. Press **Finish** when you are done.

Words you don't tap are not marked at all; they may come back in a later session. At level C2 there is nothing to calibrate.

Calibration needs the CEFR [dictionaries](../reference/dictionaries.md).

## Word order in Review

**Settings → Vocabulary → Usage priority** sets the order of usage groups in Review: neutral, informal, formal, specialized, connotation, old-fashioned, offensive and other. Drag the groups to reorder them. Words from groups higher in the list are suggested first.
