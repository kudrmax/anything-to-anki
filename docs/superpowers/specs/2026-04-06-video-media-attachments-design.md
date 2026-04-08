# Video Media Attachments Design

**Date:** 2026-04-06
**Status:** Approved

## Overview

Add video file support to anything-to-anki. From a video file the system extracts subtitles, maps each word candidate to subtitle timecodes, and lazily generates a screenshot and audio clip per candidate via a batch job — analogous to how meanings are generated.

Three phases, implemented in order:
1. Extract subtitles from video → feed into existing subtitle flow
2. Map each candidate to subtitle timecodes (`media_start_ms`, `media_end_ms`)
3. Batch job that generates screenshot + audio clip per candidate

---

## Domain

### SourceType

Add `VIDEO = "video"` to `SourceType`.

### Source

Add one field:
```python
video_path: str | None = None   # absolute path to original video file on disk
```

`raw_text` for VIDEO sources always contains SRT text — either from an attached `.srt` file or extracted from the embedded track at creation time. No track index is stored after creation.

### StoredCandidate

Add four fields:
```python
media_start_ms: int | None = None   # start of covering subtitle range
media_end_ms: int | None = None     # end of covering subtitle range
screenshot_path: str | None = None  # absolute path to generated screenshot
audio_path: str | None = None       # absolute path to generated audio clip
```

### SubtitleBlock (new frozen dataclass — domain/value_objects)

```python
@dataclass(frozen=True)
class SubtitleBlock:
    start_ms: int
    end_ms: int
    char_start: int  # start offset of this block's cleaned text in the full cleaned_text
    char_end: int    # end offset (exclusive)
```

### ParsedSrt (new frozen dataclass — domain/value_objects)

```python
@dataclass(frozen=True)
class ParsedSrt:
    text: str                      # full cleaned text ready for SpaCy
    blocks: list[SubtitleBlock]    # ordered, non-overlapping, gaps allowed (skipped blocks)
```

### SubtitleTrackInfo (new frozen dataclass — domain/value_objects)

```python
@dataclass(frozen=True)
class SubtitleTrackInfo:
    index: int
    language: str | None   # e.g. "eng", "rus"
    title: str | None      # e.g. "English (SDH)"
    codec: str             # e.g. "subrip", "ass"
```

### MediaExtractionJob (new entity — domain/entities)

```python
@dataclass
class MediaExtractionJob:
    source_id: int | None          # None = all sources
    status: MediaExtractionJobStatus
    total_candidates: int
    candidate_ids: list[int]       # snapshot at job creation time
    processed_candidates: int = 0
    failed_candidates: int = 0
    skipped_candidates: int = 0    # no video_path or no timecodes
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    id: int | None = None
```

### MediaExtractionJobStatus (new enum — domain/value_objects)

`PENDING`, `RUNNING`, `DONE`, `FAILED`

### New Ports (domain/ports)

**SubtitleExtractor (ABC):**
```python
def list_tracks(self, video_path: str) -> list[SubtitleTrackInfo]
    """Return all subtitle tracks embedded in the video."""

def extract(self, video_path: str, track_index: int) -> str
    """Extract subtitle track as raw SRT text."""
```

**MediaExtractor (ABC):**
```python
def extract_screenshot(self, video_path: str, timestamp_ms: int, out_path: str) -> None
    """Write a JPEG screenshot at the given timestamp."""

def extract_audio(self, video_path: str, start_ms: int, end_ms: int, out_path: str) -> None
    """Write an MP3 audio clip for the given range."""
```

**MediaExtractionJobRepository (ABC):** standard CRUD, same shape as `GenerationJobRepository`.

---

## Subtitle Parsing — Structured Flow

`RegexSrtParser` gains a second method `parse_structured(raw_text: str) -> ParsedSrt`.

**Algorithm:**

```
cleaned_text = ""
blocks = []

for each SRT block (sequence number + timecode + text lines):
    parse start_ms, end_ms from timecode line
    apply all existing cleaning rules to text lines:
        - strip positional tags, HTML tags
        - skip sound description lines
        - remove speaker labels
        - skip credits blocks entirely
    cleaned_block = join remaining lines
    if cleaned_block is empty:
        continue  # block vanished after cleaning — no SubtitleBlock created
    char_start = len(cleaned_text)
    cleaned_text += cleaned_block + "\n"
    char_end = len(cleaned_text)  # exclusive, includes the \n
    blocks.append(SubtitleBlock(start_ms, end_ms, char_start, char_end))

return ParsedSrt(text=cleaned_text.rstrip(), blocks=blocks)
```

The existing `parse()` method becomes a thin wrapper: `return self.parse_structured(raw_text).text`.

---

## Timecode Mapping

After `AnalyzeTextUseCase` produces candidates from `ParsedSrt.text`, for each candidate:

```python
pos = cleaned_text.find(context_fragment)
if pos == -1:
    # fallback: skip timecodes for this candidate
    continue
frag_start = pos
frag_end = pos + len(context_fragment)

covering = [
    b for b in blocks
    if b.char_start < frag_end and b.char_end > frag_start
]
if covering:
    candidate.media_start_ms = min(b.start_ms for b in covering)
    candidate.media_end_ms = max(b.end_ms for b in covering)
```

If `context_fragment` is not found (edge case: SpaCy reconstructs text with different whitespace), the candidate is stored without timecodes — it will be skipped during media extraction.

---

## Source Creation with Video — CreateSourceUseCase

`SubtitleExtractor` is used **only here**, at creation time. By the time processing starts, `raw_text` already contains the final SRT content.

**POST /sources — video upload flow:**

1. Client sends video file (+ optional `.srt` file) as multipart.
2. Video file is saved to disk; `video_path` is recorded.
3. If `.srt` is present: `raw_text = srt_file_content`. Done.
4. If no `.srt`: `CreateSourceUseCase` calls `SubtitleExtractor.list_tracks(video_path)`.
   - 0 tracks → raise error: "No subtitles found. Please attach a .srt file."
   - 1 track → call `SubtitleExtractor.extract(video_path, track_index)` → `raw_text = extracted_srt`.
   - 2+ tracks → return `HTTP 200` with `{status: "subtitle_selection_required", tracks: [...]}`.
5. Client shows track selection dialog, user picks a track.
6. Client re-submits with chosen `track_index` → `CreateSourceUseCase` extracts that track → `raw_text = extracted_srt`.
7. Source is saved: `source_type=VIDEO`, `video_path=...`, `raw_text=<SRT content>`.

`SubtitleExtractor` is **not injected** into `ProcessSourceUseCase`. Processing always reads `raw_text`.

---

## ProcessSourceUseCase — VIDEO path

Add `ProcessingStage.MAPPING_TIMECODES`.

```
Stage 1: CLEANING_SOURCE
    if source_type in (VIDEO, SUBTITLES):
        parsed = srt_parser.parse_structured(source.raw_text)  # returns ParsedSrt
    else:
        run existing parser or use raw_text as-is

Stage 2: ANALYZING_TEXT
    result = analyze_text_use_case.execute(parsed.text or raw_text)

Stage 3: MAPPING_TIMECODES  (VIDEO only)
    for each candidate:
        compute media_start_ms / media_end_ms via covering-blocks algorithm

Stage 4: save candidates with timecodes, update source status to DONE
```

---

## Media Extraction Job

### CreateMediaExtractionJobUseCase

Accepts `source_id: int | None`. Collects candidates where:
- `media_start_ms is not None` (has timecodes)
- `screenshot_path is None` (not yet generated)
- `status == LEARN`

Creates `MediaExtractionJob` with snapshot of those `candidate_ids`.

### ExecuteMediaExtractionJobUseCase

Iterates `candidate_ids`. For each:
1. Load candidate + its source (to get `video_path`).
2. If `video_path` is None or file does not exist → mark as skipped.
3. Compute output paths:
   - `{media_root}/{source_id}/{candidate_id}_screenshot.jpg`
   - `{media_root}/{source_id}/{candidate_id}_audio.mp3`
4. `screenshot_timestamp_ms = (media_start_ms + media_end_ms) // 2`
5. Call `media_extractor.extract_screenshot(...)` and `extract_audio(...)`.
6. Update `candidate.screenshot_path` and `candidate.audio_path`.
7. Increment `processed_candidates` (or `failed_candidates` on error).

`media_root` comes from settings (default: `~/.anything-to-anki/media`).

### Media HTTP Endpoint

`GET /media/{source_id}/{filename}` — serves files from `{media_root}/{source_id}/`.

---

## Infrastructure

**FfmpegSubtitleExtractor** — uses `ffprobe -v quiet -print_format json -show_streams` to list tracks; `ffmpeg -i {input} -map 0:s:{index} -f srt {output}` to extract.

**FfmpegMediaExtractor:**
- Screenshot: `ffmpeg -ss {ts_s} -i {input} -vframes 1 -q:v 2 {out}.jpg`
- Audio: `ffmpeg -ss {start_s} -to {end_s} -i {input} -vn -acodec mp3 {out}.mp3`

Both require `ffmpeg` installed on the host. If missing → clear error message to user.

New DB models: `media_extraction_jobs` table (mirrors `generation_jobs` shape) + migrations for new columns on `sources` and `candidates`.

---

## Frontend Changes

### InboxPage

- If backend returns `subtitle_selection_required` → show modal with track list (language + title + codec). User picks one, form re-submits.
- File detection badge already handles "Video + subtitles" / "Video · mp4" cases.

### SourceCard

- New "Generate media" button for `VIDEO` sources, analogous to "Generate meanings".
- Active when: source has candidates with timecodes but no media files.
- Shows job progress while running.

### ReviewPage — screenshot popover

- On `context_fragment` block hover → show popover with screenshot (if `screenshot_url` present).
- Popover also shows a play button for the audio clip.
- If no screenshot yet → no popover (not a loading state, just absent).

### CardPreviewDTO

Add:
```python
screenshot_url: str | None = None
audio_url: str | None = None
```

### Anki Export

- `Screenshot` field: `<img src="...">` (image copied to Anki media folder).
- `Audio` field: `[sound:filename.mp3]` (audio copied to Anki media folder).

---

## Testing

- `tests/unit/domain/` — `SubtitleBlock`, `ParsedSrt`, timecode mapping algorithm (pure logic, no mocks)
- `tests/unit/application/` — `ProcessSourceUseCase` for VIDEO type (mock `SubtitleExtractor`, `MediaExtractor`); `ExecuteMediaExtractionJobUseCase` (mock `MediaExtractor`)
- `tests/unit/application/` — `RegexSrtParser.parse_structured()` — verify `char_start`/`char_end` correctness after cleaning, skipped blocks, credits removal
