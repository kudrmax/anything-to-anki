# Meaning image: a second picture on the card

## Problem

A card has one picture field. A video frame belongs on the front: it is the
scene the phrase came from. A picture of the target (a drain for "drain") is
the meaning shown as a picture and belongs on the back. Today a picture picked
from the search results or pasted with Cmd+V replaces the frame, deletes its
file and lands on the front of the card. Seven notes already went to Anki
this way.

## Decisions

- **Two independent pictures.** `CandidateMedia.screenshot_path` is only the
  video frame. The meaning image is its own 1:1 entity
  `CandidateMeaningImage` in its own table, so media extraction never touches
  it.
- A picture picked from the search results or pasted is always the meaning
  image. A new one replaces the previous meaning image; the frame stays.
- Regenerating media no longer deletes the picked picture.
- "Del images" and media stats in Settings cover both kinds of pictures.
  Reprocessing a source keeps the meaning image like the other enrichments.
- Alembic migration moves rows whose `screenshot_path` is a picked picture
  (`{id}_screenshot.{digest}.webp`) to the new table and clears their
  `screenshot_path`. Files stay where they are. Lost frames are not restored.

## Anki: one set of fields for both note types

- Recognition and cloze note types share one `AnkiFieldNames` read from the
  same settings. The only difference is the cloze logic: the phrase field
  carries the cloze markup and the cloze type also has a Hint field.
- New settings: `anki_field_meaning_image` (`MeaningImage`), `anki_field_hint`
  (`Hint`), `anki_cloze_note_type` (`AnythingToAnkiCloze`).
- The cloze phrase field is the shared sentence field (`Sentence`), not `Text`.
- Cloze templates use the same `%FIELD_…%` placeholders and the same field map.
- The app creates only its own default note types, as before. Templates are
  not synced to Anki: Settings → Card template shows the templates of both
  types to copy by hand.
- Templates: front — frame and audio; back — frame and audio on top, the
  meaning image under Meaning.

## UI

Review shows the frame with audio in the left column, as now. The meaning
image is shown under the definition in the right column, without a label.
Export is unchanged.

## Fixing the user's Anki (one-off, by hand)

1. Note type `Main`: add the `MeaningImage` field and one line under Meaning
   in the back template; the rest of the hand-edited template stays.
2. Seven notes (scatter, eel, limb, creak, grin, sulfur, scattered): move
   `Image` to `MeaningImage` and clear `Image`.
3. `Main Close` is the user's old hand-made type and is left alone.
