# Settings

Open **Settings** in the top right corner, or press `⌘,` (`Ctrl+,` outside macOS) on any screen. The sections are listed on the left.

**Save settings** saves the whole form, not only the open section. Theme, auto-play, usage priority and the word lists are saved at once, without the button.

## Appearance

**Theme**: **Light**, **Dark** (default) or **System**, which follows macOS. The theme is stored in the browser, so each browser and the [macOS app](macos-app.md) keep their own.

## Anki

| Setting | Default | What it does |
|---|---|---|
| **Deck name** | `Default` | The deck cards are added to. Created if missing |
| **Note type** | `AnythingToAnkiType` | Note type for regular cards. The default one is created automatically |
| **Cloze note type** | `AnythingToAnkiCloze` | Note type for cloze cards. Your own must be a cloze type with the same fields |
| **Field mapping** | Field names as in [Fields](anki-export.md#fields) | Which Anki field each part of the card goes to |

**In Anki** checks both note types in the running Anki. It shows **✓ Ready**, or a **Create note type** / **Add missing fields** button.

**Card template** copies the app's card templates with your field names, ready to paste into Anki. See [Card templates](anki-export.md#card-templates).

## Vocabulary

| Setting | Default | What it does |
|---|---|---|
| **Target CEFR level** | B1 | Your level. Words above it are suggested |
| **Frequent words** | Auto | How common a word must be to count as probably known |
| **Vocabulary calibration** | — | Builds a word list and opens [calibration](vocabulary.md#calibration) |
| **Usage priority** | neutral first | Order of usage groups in Review. Drag to reorder |

Changing the level or the frequent-words threshold re-analyses every source. See [Your vocabulary and level](vocabulary.md).

## Review

| Setting | Default | What it does |
|---|---|---|
| **Auto-play audio** | On | Plays the card's audio when it opens. Stored in the browser |
| **Default cloze hint** | No hint | The hint preselected when you make a [cloze card](review.md#cloze-cards) |

## AI model

**Claude**: **Haiku**, **Sonnet** (default) or **Opus**. The model is used for every AI feature: meanings, follow-ups, polish and topic words. Each option is the latest model of that family available to your Claude Code login.

Opus gives the best results and uses the most of your plan; Haiku is the fastest and uses the least.

## Text-to-speech

| Setting | Default | What it does |
|---|---|---|
| **Speed** | 1.0× | Speech speed, 0.5× to 2.0× |
| **Enabled voices** | All 28 | Each phrase is read by a random voice from the checked ones: American and British, female and male |

Speech is generated locally with [Kokoro](https://github.com/hexgrad/kokoro). The settings apply to speech generated after the change.

## Pictures

**Pictures per source** (default 12): how many results each image source (Wiktionary, Bing, Yandex) returns when you look for a picture of a word.

## Books

**Default titles** (default `{{collection}} ch{{n}}`): the naming rule used when one add makes several sources. `{{collection}}` is the collection name, `{{n}}` is the number, and `{{title}}` is the file's or chapter's own title. See [Naming several sources](sources.md#naming-several-sources).

## Known words

Every word you know, with a search box. Remove a word (×) to make it new again in every source. See [Known words](vocabulary.md#known-words).

## Learning

Words you are learning: **In Anki** (with the day each becomes known) and **Waiting for export**. Read-only. See [Learning](vocabulary.md#learning).

## Unknown words

Words you told the app you don't know. Remove a word (×) to take it off the list. See [Unknown words](vocabulary.md#unknown-words).

## Media storage

How much disk space the screenshots and audio of each video source take. **Del images**, **Del audio** and **Del all** delete them for one source.

Deleting is permanent. Deleted audio makes cards without TTS **Incomplete** for export; you can cut the media again with **✨ → Media**, as long as the video is still on disk.
