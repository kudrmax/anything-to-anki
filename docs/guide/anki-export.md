# Export to Anki

Cards you mark **Learn** or **Cloze** go to [Anki](https://apps.ankiweb.net/) through the AnkiConnect add-on. To set up Anki, see [Installation → Anki](../getting-started/installation.md#4-anki-and-ankiconnect).

![Export screen](../images/export.png)

## Exporting

1. Start Anki. It must stay open during the export.
2. Open **Export** in the top bar to export everything. To export one source or collection, use **Export** in its menu or **Export N** on the Review screen.
3. Check the header: it should say **Anki connected**.
4. Press **Add to Anki · N cards**.

The result shows how many cards were **added**, how many were **already in Anki**, and how many **failed**.

The badge on **Export** in the top bar shows how many words are waiting to be exported.

### Ready and Incomplete

The cards are split into two groups:

- **Ready**: the card has a meaning and audio of the phrase (a video clip or TTS). A cloze card also needs hidden words.
- **Incomplete**: something is missing. The row says what: **No meaning**, **No audio** or **No cloze words**. Click a row to open the card in Review and fill it in.

**Export incomplete · N cards** sends incomplete cards anyway. The missing parts are left empty in Anki.

### What happens after export

- Each word is exported **once**: one note per word, with the phrase where you decided it.
- Every note gets the tag `anything-to-anki`. Media files (screenshots, audio, pictures) are copied into Anki.
- A word that is already in Anki (same note type, same target) is not added twice. It is counted as **already in Anki**.
- An exported word counts as **Learning**. **30 days after export** it becomes **Known** and is no longer suggested in new sources. You can see these words in [Settings → Learning](settings.md#learning).

Changes you make in the app after export (a new meaning, new audio) **do not** reach notes already in Anki. Edit the note in Anki instead.

## Note types and deck

The app needs two note types in Anki: one for regular cards and one for cloze cards. With the default settings you don't have to create anything:

| | Default name | Created automatically |
|---|---|---|
| Regular cards | `AnythingToAnkiType` | Yes, on the first export |
| Cloze cards | `AnythingToAnkiCloze` | Yes, on the first export |
| Deck | `Default` | Yes, if missing |

Change the names in [Settings → Anki](settings.md#anki).

### Using your own note type

You can export into a note type of your own, for example to match an existing deck:

1. Enter its name in **Settings → Anki → Note type** (or **Cloze note type**; that one must be an Anki cloze type).
2. Map the app's fields to your field names in **Field mapping**, then press **Save settings**.
3. Check the **In Anki** block. If the type is missing or lacks fields, use **Create note type** or **Add missing fields**.

The app never changes your own note type during export. If the type is missing, or lacks a field the export fills, **nothing is exported**, and a banner appears at the top of every screen: **Export to Anki is blocked: cards would lose their content**. Fix it with the link in the banner.

**Add missing fields** adds the fields, but not to your card templates. Add them to the templates yourself, or copy the app's templates (see below).

### Fields

Both note types use the same fields:

| Field | Contents |
|---|---|
| `Sentence` | The phrase with the target in bold. On a cloze card, the phrase with `{{c1::…}}` gaps |
| `Target` | The word in dictionary form |
| `Meaning` | AI definition and context |
| `IPA` | Transcription |
| `Translation` | Short translation |
| `Synonyms` | Synonyms |
| `Examples` | Example sentences |
| `Image` | Video frame |
| `MeaningImage` | The picture you chose for the word |
| `Audio` | Audio clip of the phrase from the video |
| `AudioTargetUS`, `AudioTargetUK` | Dictionary pronunciation of the word |
| `AudioTTS` | The phrase read aloud by TTS |

### Card templates

The templates live in [`anki-templates/`](../../anki-templates):

- The **regular card** front shows the video frame, plays the phrase audio, and shows the phrase. The back adds the word, IPA, pronunciation, meaning, picture, translation, synonyms and examples.
- The **cloze card** front shows only the video frame and the phrase with gaps. It has no audio, because audio would give the answer away. The back is like the regular back.
- Both support Anki's night mode.

To restyle cards, or to fix a note type whose fields you renamed, open **Settings → Anki → Card template**. Use **Copy Front**, **Copy Back**, **Copy Cloze Front**, **Copy Cloze Back** and **Copy CSS**, and paste the result into Anki's template editor. The copies use your current field names.

The app writes templates only when it creates a note type. If you rename fields later, re-paste the templates, or that part of the card stops showing.

## Problems

| What you see | What to do |
|---|---|
| **Launch Anki with AnkiConnect to sync**, **Anki unavailable** | Start Anki. Check that AnkiConnect is installed: **Tools → Add-ons** in Anki |
| **Export to Anki is blocked: cards would lose their content** | Your own note type is missing or lacks fields. Follow **Fix in Settings → Anki** |
| A card **failed** | See `make logs` for Anki's reason |
