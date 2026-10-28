# Settings

Open **Settings** in the top right corner, or press `⌘,` (`Ctrl+,` outside macOS) on any screen. The sections are listed on the left; on a phone they scroll in a row above the page.

| Section | What is in it |
|---|---|
| [General](#general) | Theme, version and updates |
| [Words](#words) | Your level, frequent words, calibration, usage priority |
| [My words](#my-words) | Known, learning and unknown words |
| [Cards](#cards) | Card layout, AI model, audio, pictures, cloze hint |
| [Anki](#anki) | Deck, note types, fields and templates |
| [Sources](#sources) | Default titles, media storage |

Every change is saved on its own: **Saved** shows next to the section title for a moment. Text is saved when you leave the field or press Enter. If a change cannot be saved, the reason shows there instead and the change is sent again with the next one.

**Your level** and **Frequent words** analyse every source again, so they ask first: **Analyse again** applies the new value, **Cancel** keeps the old one.

## General

**Theme**: **Light**, **Dark** (default) or **System**, which follows macOS. The theme is stored in the browser, so each browser and the [macOS app](macos-app.md) keep their own.

**Updates** shows the installed version. **Changelog** opens the full history of releases. **Check for updates** looks for a new release right now, without waiting for the daily check. If there is one, the update window opens; if not, you see "You're on the latest version". See [Updating](updating.md).

![Settings → General](../images/updating/settings-updates.png)

## Words

| Setting | Default | What it does |
|---|---|---|
| **Your level** | B2 | The CEFR level you are learning. Words of this level and harder are suggested |
| **Frequent words** | Auto | How common a word must be to count as probably known |
| **Calibration** | — | Builds a word list and opens [calibration](vocabulary.md#calibration) |

See [Your vocabulary and level](vocabulary.md).

**Usage priority** (default: neutral first): words from groups higher up are suggested first. Drag to reorder.

## My words

Three tabs, each with the number of words in it. Each tab is a table, newest first, with a search box over all of its words. It shows 50 words; **Show 50 more** adds the next ones.

- **Known**: the word, its part of speech and the day it became known. Words that became known by themselves say **after 30 days in Anki**. Remove a word (× at the end of its row) to make it new again in every source. See [Known words](vocabulary.md#known-words).
- **Learning**: words you are learning: **Waiting for export**, or **In Anki** with the day each becomes known. Read-only. See [Learning](vocabulary.md#learning).
- **Unknown**: words you told the app you don't know, with the day you added each. Remove a word (×) to take it off the list. See [Unknown words](vocabulary.md#unknown-words).

On a phone the part of speech is left out.

## Cards

Everything about the card you review.

| Setting | Default | What it does |
|---|---|---|
| **Card layout** | — | **Open the editor** arranges the review card, see below |
| **AI model** | Sonnet | **Haiku**, **Sonnet** or **Opus**: the latest model of that family available to your Claude Code login. Used for every AI feature: meanings, follow-ups, polish and topic words. Opus gives the best results and uses the most of your plan; Haiku is the fastest and uses the least |
| **Auto-play** | On | Plays the card's audio when it opens. Stored in the browser |
| **Speech speed** | 1.0× | Text-to-speech speed, 0.5× to 2.0× |
| **Voices** | All 28 | Each phrase is read by a random voice from the selected ones. Grouped: American female, American male, British female, British male |
| **Choices per source** | 12 | How many pictures each image source (Wiktionary, Bing, Yandex) offers when you pick a picture for a word |
| **Default hint** | No hint | The hint preselected when you make a [cloze card](review.md#cloze-cards) |

Speech is generated locally with [Kokoro](https://github.com/hexgrad/kokoro). The speech settings apply to speech generated after the change.

### Card layout

Arrange the body of the card on the [Review](review.md) screen: everything between the phrase and the bottom bar. The phrase, **Learn** / **Cloze** / **Know** / **Skip** and the card tools stay where they are. Changes are saved at once and apply to Review the next time you open it. Anki cards are not affected.

The editor is the Review screen itself on a sample card, with the card layout editor in a window on top. **Sample card has** in the window switches what the card has: **Meaning**, **US / UK audio**, **TTS**, **Video frame**, **Picture**, **Picture choice** (the suggested pictures shown while no picture is chosen; it turns **Picture** off, turns the picture suggestions on, and the other way round). The card shows exactly what a card like that shows on Review: **Meaning** off shows **Generate meaning** in place of the meaning, and a block with nothing to show is not drawn. Show or hide the source text, the phrase list and the picture suggestions with their buttons, as on Review; the other buttons do nothing on the sample.

On the card:

- **Drag a block** between rows to give it a row of its own, or next to another block to put them in one row. Blocks in a row wrap when the column is too narrow.
- **Drag a block to Hidden blocks** to hide it. Drag it back onto the card to show it again; it keeps its style.
- **Drag Divider** from **Add** between rows to add a line across the column. Drag a line to move it, or to **Hidden blocks** to remove it. Click a line to choose what it **Sticks to** when rows move to the bottom of the column: **Row below** (the default) moves the line down with them, **Row above** keeps it under the rows above.
- **Click a block** to change how it looks (click an empty spot or press Esc to see the card without the selection): **Size** (XS to XL), **Colour** (**Main**, **Grey**, **Light grey**, **Accent**) and **Bold** for text; **Size** for the video frame and picture; for every block **In its row** (**Left** or **Right**), **Vertically** (**Text line**, the default, puts blocks of different sizes on one line of text; **Top**, **Middle**, **Bottom**) and **Space around** (extra room **Above**, **Below**, **Left** and **Right**). Blocks set to **Right** stand together at the right end of the row. In the same way **Bottom** moves the row of the block and the rows below, with the line right above it unless that line sticks to the row above, down to the bottom of the column; next to other blocks of its row it stands at their bottom.
- **Columns** in the window: up to three, each with its width (**Narrow**, **Normal**, **Wide**); × removes a column and moves its blocks to the column before it. **Add column** adds one on the right.

The phone button in the window shows the same Review screen as it is on a phone; change the layout on the desktop screen. **×** closes the editor.

**Reset to default** brings back the original layout. On a phone the first column is shown on the card and the other columns fold into **Details**.

| Block | What it shows |
|---|---|
| **Target word** | The word, phrasal verb or collocation |
| **Translation** | Translation of the target |
| **Meaning in context** | Second line of the meaning: what the target means in this phrase |
| **Definition** | First line of the meaning |
| **More meaning** | Anything the meaning adds after its first two lines; most cards have none |
| **Synonyms**, **Examples**, **Transcription** | As named. Hover an example to use it as the phrase |
| **US / UK audio**, **TTS audio** | Pronunciation and text-to-speech buttons |
| **Level and frequency** | CEFR level or phrasal verb, frequency and register |
| **Video frame**, **Picture** | The clip from the video and the picture of the target |
| **Picture choice** | Suggested pictures to pick from while the card has no picture |
| **Generate meaning** | Progress, **Generate meaning** or **Retry** while the card has no meaning |

A block with nothing to show on a card is left out on that card. A line is drawn only between rows that show something: two lines left next to each other merge into one, and there is none at the top or bottom of a column. A column with nothing to show is left out, and the other columns take its room.

## Anki

| Setting | Default | What it does |
|---|---|---|
| **Deck** | `Default` | The deck cards are added to. Created if missing |
| **Note type** | `AnythingToAnkiType` | Note type for regular cards. The default one is created automatically |
| **Cloze note type** | `AnythingToAnkiCloze` | Note type for cloze cards. Your own must be a cloze type with the same fields |

Each note type is checked in the running Anki: **✓ In Anki**, or a **Create note type** / **Add missing fields** button next to it. If Anki is not running, a line under them says so.

**Fields and templates** is folded: it matters only for your own note type. Open it to map each part of the card to a field of your note type (defaults as in [Fields](anki-export.md#fields)) and to copy the card templates with your field names: **Copy Front**, **Copy Back**, **Copy Cloze Front**, **Copy Cloze Back**, **Copy CSS**. See [Card templates](anki-export.md#card-templates).

## Sources

**Default titles** (default `{{collection}} ch{{n}}`): the naming rule used when one add makes several sources. `{{collection}}` is the collection name, `{{n}}` is the number, and `{{title}}` is the file's or chapter's own title. See [Naming several sources](sources.md#naming-several-sources).

**Media storage** is a table of video sources with the space their **Images** (screenshots) and **Audio** take, and how many files each has. The bin button on a row deletes **Images**, **Audio** or **All** for that source. **Refresh** recounts.

Deleting is permanent. Deleted audio makes cards without TTS **Incomplete** for export; you can cut the media again with **✨ → Media**, as long as the video is still on disk.
