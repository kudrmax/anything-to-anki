# Your vocabulary and level

The app suggests only words that are new to you. It decides what is new from three things: your **level**, your **known words** and how **frequent** a word is.

## Level

**Settings → Words → Your level** is the level you are learning now, from A1 to C2. The default is **B2**. Words of your level and harder are suggested for learning; easier words are treated as known. Function words such as *to*, *have* or *will* are never suggested. If you are in the middle of A2, choose **A2**. If you are just starting and know only a few dozen words, choose **A1**.

Set it before you add your first sources. Changing it later re-analyses **every** source: the app runs **Find words again** on all of them as one operation, behind the progress overlay. Your decisions are kept.

## Known words

A word becomes **known** in three ways:

- you press **Know** on one of its cards;
- you mark it during [calibration](#calibration);
- 30 days pass after you export it to Anki.

A known word is never suggested again, in any source. Known is decided per word: knowing `run` as a verb also covers `run` as a noun.

To undo it, remove the word in **Settings → Words → Your words → Known**. Its cards become new again everywhere.

## Learning

Words you marked **Learn** or **Cloze** are **learning**. They are not suggested as new either. **Settings → Words → Your words → Learning** lists them:

- **In Anki**: exported, with the day each one becomes known.
- **Waiting for export**: marked, but not in Anki yet.

## Unknown words

**Unknown words** are the opposite of known words: words you told the app you don't know. You add them with the **Unknown words** button (`U`) on a card. A phrase that contains an unknown word (other than its target) never counts as **Ready**. Manage the list in **Settings → Words → Your words → Unknown**.

## Frequent words

Very common words are probably known to you, even at your level or harder. **Settings → Words → Frequent words** sets how common a word must be to go to the **Probably known** section in Review. These words are moved down, not removed.

| Option | Example words at that level |
|---|---|
| **Auto** (default) | Starts from your level, then learns from your **Learn** and **Know** presses |
| 4.0 | naked, divorce, awkward, hilarious |
| 4.5 | concept, classic, assume, weird |
| 5.0 | career, issue, available, figure out |
| 5.5 | end up, find out, come in, get out |
| **Off** | Nothing goes down for being frequent |

Auto starts where a learner of your level probably knows a word: 5.5 at A2 and B1, 5.0 at B2, 4.5 at C1, 4.0 at C2. At A1 it starts with nothing going down, since a beginner may not know even the most common words; it comes down to 5.5 once you mark most of the words that common **Know**. A beginner keeps everyday words of their level on top; an advanced learner sends the common ones down. Then it moves one step at a time: down while the words just below are mostly marked **Know**, up while the words just above are mostly marked **Learn**. A step needs at least four marked words to move.

The numbers are [Zipf frequencies](https://github.com/rspeer/wordfreq#usage): 6 is a very common word, 3 is a rare one. Changing this setting re-analyses every source, like a level change.

## Calibration

A new user knows thousands of words above their level that the app doesn't know about. Calibration lets you mark many of them as known quickly.

1. Open **Settings → Words → Calibration** and press **Prepare**. The app builds a word list from the dictionaries; this takes a moment.
2. Press **Calibrate**.
3. Each round shows up to 15 words of your level and the two above it. Tap every word you know, then press **Next N words**.
4. Press **Finish** when you are done.

Words you don't tap are not marked at all; they may come back in a later session.

Calibration needs the CEFR [dictionaries](../reference/dictionaries.md).

## Word order in Review

**Settings → Words → Usage priority** sets the order of usage groups in Review: neutral, informal, formal, specialized, connotation, old-fashioned, offensive and other. Drag the groups to reorder them. Words from groups higher in the list are suggested first.
