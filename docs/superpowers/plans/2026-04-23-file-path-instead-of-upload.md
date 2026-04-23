# File Path Instead of Upload — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace multipart file upload with file path input — backend reads files from disk directly, video files are not copied.

**Architecture:** New port `FileReader` for file I/O. New use case method `execute_from_file()` determines file type and delegates. New API endpoint `POST /sources/file` replaces `POST /sources/video`. Frontend replaces drag-and-drop with a text input for file path.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (frontend), pydantic (DTOs)

---

### Task 1: FileReader port + adapter

**Files:**
- Create: `backend/src/backend/domain/ports/file_reader.py`
- Create: `backend/src/backend/infrastructure/adapters/local_file_reader.py`
- Create: `backend/tests/unit/infrastructure/test_local_file_reader.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/infrastructure/test_local_file_reader.py
import os
import tempfile

import pytest
from backend.infrastructure.adapters.local_file_reader import LocalFileReader


@pytest.mark.unit
class TestLocalFileReader:
    def test_exists_returns_true_for_existing_file(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello")
            path = f.name
        try:
            reader = LocalFileReader()
            assert reader.exists(path) is True
        finally:
            os.unlink(path)

    def test_exists_returns_false_for_missing_file(self) -> None:
        reader = LocalFileReader()
        assert reader.exists("/nonexistent/path/file.txt") is False

    def test_read_text_returns_file_content(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            path = f.name
        try:
            reader = LocalFileReader()
            assert reader.read_text(path) == "hello world"
        finally:
            os.unlink(path)

    def test_read_text_raises_for_missing_file(self) -> None:
        reader = LocalFileReader()
        with pytest.raises(FileNotFoundError):
            reader.read_text("/nonexistent/path/file.txt")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/unit/infrastructure/test_local_file_reader.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create the port**

```python
# backend/src/backend/domain/ports/file_reader.py
from __future__ import annotations

from abc import ABC, abstractmethod


class FileReader(ABC):
    """Reads files from the local filesystem."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if file exists at path."""

    @abstractmethod
    def read_text(self, path: str) -> str:
        """Read file content as text. Raises FileNotFoundError if missing."""
```

- [ ] **Step 4: Create the adapter**

```python
# backend/src/backend/infrastructure/adapters/local_file_reader.py
from __future__ import annotations

from pathlib import Path

from backend.domain.ports.file_reader import FileReader


class LocalFileReader(FileReader):
    """Reads files from local filesystem using pathlib."""

    def exists(self, path: str) -> bool:
        return Path(path).is_file()

    def read_text(self, path: str) -> str:
        p = Path(path)
        if not p.is_file():
            msg = f"File not found: {path}"
            raise FileNotFoundError(msg)
        return p.read_text(encoding="utf-8", errors="replace")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/unit/infrastructure/test_local_file_reader.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/backend/domain/ports/file_reader.py backend/src/backend/infrastructure/adapters/local_file_reader.py backend/tests/unit/infrastructure/test_local_file_reader.py
git commit -m "feat: add FileReader port and LocalFileReader adapter"
```

---

### Task 2: `execute_from_file()` use case method

**Files:**
- Modify: `backend/src/backend/application/use_cases/create_source.py`
- Create: `backend/tests/unit/application/test_create_file_source.py`

**Context:** `execute_from_file()` determines file type by extension. Video extensions → delegates to existing `execute_video()` logic. Text extensions → reads content via `FileReader` and delegates to existing `execute()`. The method needs `FileReader` as a new dependency in the constructor.

Video extensions: `.mp4`, `.mkv`, `.avi`, `.mov`
Text extensions: everything else (`.txt`, `.srt`, `.html`, `.epub`, etc.)

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/application/test_create_file_source.py
from unittest.mock import MagicMock

import pytest
from backend.application.dto.video_dtos import TrackSelectionRequired, VideoSourceCreated
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


def _make_source_repo(source_id: int = 1) -> MagicMock:
    repo = MagicMock()
    created = MagicMock()
    created.id = source_id
    repo.create.return_value = created
    return repo


def _make_file_reader(content: str = "file content", exists: bool = True) -> MagicMock:
    reader = MagicMock()
    reader.exists.return_value = exists
    reader.read_text.return_value = content
    return reader


def _make_subtitle_extractor(tracks: list[SubtitleTrackInfo] | None = None) -> MagicMock:
    extractor = MagicMock()
    extractor.list_tracks.return_value = tracks or []
    extractor.extract.return_value = "1\n00:00:01,000 --> 00:00:02,000\nHello.\n"
    return extractor


def _make_audio_lister() -> MagicMock:
    lister = MagicMock()
    lister.list_audio_tracks.return_value = []
    return lister


@pytest.mark.unit
class TestExecuteFromFile:
    def test_text_file_reads_content_and_creates_source(self) -> None:
        repo = _make_source_repo()
        repo.create.return_value = Source(
            id=1, raw_text="hello", status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        reader = _make_file_reader(content="hello")
        uc = CreateSourceUseCase(source_repo=repo, file_reader=reader)

        result = uc.execute_from_file(file_path="/home/user/doc.txt")

        assert isinstance(result, Source)
        assert result.id == 1
        reader.read_text.assert_called_once_with("/home/user/doc.txt")

    def test_srt_file_creates_source_with_subtitles_input_method(self) -> None:
        repo = _make_source_repo()
        repo.create.return_value = Source(
            id=1, raw_text="srt content", status=SourceStatus.NEW,
            input_method=InputMethod.SUBTITLES_FILE, content_type=ContentType.TEXT,
        )
        reader = _make_file_reader(content="1\n00:00:01,000 --> 00:00:02,000\nHi\n")
        uc = CreateSourceUseCase(source_repo=repo, file_reader=reader)

        uc.execute_from_file(file_path="/home/user/subs.srt")

        created_source = repo.create.call_args[0][0]
        assert created_source.input_method == InputMethod.SUBTITLES_FILE

    def test_html_file_creates_text_source(self) -> None:
        repo = _make_source_repo()
        repo.create.return_value = Source(
            id=1, raw_text="<p>Hello</p>", status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        reader = _make_file_reader(content="<p>Hello</p>")
        uc = CreateSourceUseCase(source_repo=repo, file_reader=reader)

        uc.execute_from_file(file_path="/home/user/article.html")

        created_source = repo.create.call_args[0][0]
        assert created_source.input_method == InputMethod.TEXT_PASTED

    def test_video_file_delegates_to_execute_video(self) -> None:
        repo = _make_source_repo()
        track = SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip")
        extractor = _make_subtitle_extractor([track])
        audio = _make_audio_lister()
        reader = _make_file_reader(exists=True)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
            file_reader=reader,
        )

        result = uc.execute_from_file(file_path="/home/user/movie.mkv")

        assert isinstance(result, VideoSourceCreated)
        # Video path should be the original path, not a copy
        created_source = repo.create.call_args[0][0]
        assert created_source.video_path == "/home/user/movie.mkv"

    def test_video_with_srt_path_reads_srt(self) -> None:
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([])
        audio = _make_audio_lister()
        reader = _make_file_reader(content="1\n00:00:01,000 --> 00:00:02,000\nHi\n")
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
            file_reader=reader,
        )

        result = uc.execute_from_file(
            file_path="/home/user/movie.mp4",
            srt_path="/home/user/movie.srt",
        )

        assert isinstance(result, VideoSourceCreated)
        reader.read_text.assert_called_once_with("/home/user/movie.srt")

    def test_missing_file_raises_file_not_found(self) -> None:
        repo = _make_source_repo()
        reader = _make_file_reader(exists=False)
        uc = CreateSourceUseCase(source_repo=repo, file_reader=reader)

        with pytest.raises(FileNotFoundError, match="/nonexistent/file.txt"):
            uc.execute_from_file(file_path="/nonexistent/file.txt")

    def test_video_with_track_selection_required(self) -> None:
        repo = _make_source_repo()
        tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        extractor = _make_subtitle_extractor(tracks)
        audio = _make_audio_lister()
        reader = _make_file_reader(exists=True)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
            file_reader=reader,
        )

        result = uc.execute_from_file(file_path="/home/user/movie.mov")

        assert isinstance(result, TrackSelectionRequired)

    def test_video_with_selected_tracks(self) -> None:
        repo = _make_source_repo()
        tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        extractor = _make_subtitle_extractor(tracks)
        audio = _make_audio_lister()
        reader = _make_file_reader(exists=True)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
            file_reader=reader,
        )

        result = uc.execute_from_file(
            file_path="/home/user/movie.avi",
            subtitle_track_index=1,
            audio_track_index=0,
        )

        assert isinstance(result, VideoSourceCreated)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/unit/application/test_create_file_source.py -v`
Expected: FAIL — `execute_from_file` not found, `file_reader` not a valid parameter

- [ ] **Step 3: Add `file_reader` parameter to `CreateSourceUseCase.__init__`**

In `backend/src/backend/application/use_cases/create_source.py`, add to imports:

```python
if TYPE_CHECKING:
    from backend.domain.ports.file_reader import FileReader  # add this line
```

Modify `__init__`:

```python
def __init__(
    self,
    source_repo: SourceRepository,
    subtitle_extractor: SubtitleExtractor | None = None,
    audio_track_lister: AudioTrackLister | None = None,
    file_reader: FileReader | None = None,
) -> None:
    self._source_repo = source_repo
    self._subtitle_extractor = subtitle_extractor
    self._audio_track_lister = audio_track_lister
    self._file_reader = file_reader
```

- [ ] **Step 4: Implement `execute_from_file()` method**

Add after the existing `execute_video()` method:

```python
_VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".avi", ".mov"})

def execute_from_file(
    self,
    file_path: str,
    srt_path: str | None = None,
    title: str | None = None,
    subtitle_track_index: int | None = None,
    audio_track_index: int | None = None,
) -> Source | VideoSourceCreated | TrackSelectionRequired:
    """Create source from a local file path. Determines type by extension."""
    assert self._file_reader is not None
    if not self._file_reader.exists(file_path):
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)

    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    if f".{ext}" in self._VIDEO_EXTENSIONS:
        srt_text: str | None = None
        if srt_path is not None:
            srt_text = self._file_reader.read_text(srt_path)
        return self.execute_video(
            video_path=file_path,
            srt_text=srt_text,
            title=title,
            subtitle_track_index=subtitle_track_index,
            audio_track_index=audio_track_index,
        )

    # Text file — read content, determine input method
    content = self._file_reader.read_text(file_path)
    input_method = InputMethod.SUBTITLES_FILE if ext == "srt" else InputMethod.TEXT_PASTED
    return self.execute(raw_text=content, input_method=input_method, title=title)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/unit/application/test_create_file_source.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Run all existing tests to verify no regressions**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/unit/application/test_create_source.py backend/tests/unit/application/test_create_video_source.py -v`
Expected: PASS — existing tests unaffected (file_reader defaults to None)

- [ ] **Step 7: Commit**

```bash
git add backend/src/backend/application/use_cases/create_source.py backend/tests/unit/application/test_create_file_source.py
git commit -m "feat: add execute_from_file method to CreateSourceUseCase"
```

---

### Task 3: Wire FileReader into DI container

**Files:**
- Modify: `backend/src/backend/infrastructure/container.py:240-245`

- [ ] **Step 1: Add LocalFileReader import and instance to container**

In `backend/src/backend/infrastructure/container.py`, add import:

```python
from backend.infrastructure.adapters.local_file_reader import LocalFileReader
```

In `__init__`, add alongside existing adapters (near line 164):

```python
self._file_reader = LocalFileReader()
```

- [ ] **Step 2: Pass file_reader to create_source_use_case**

Modify `create_source_use_case` method (line 240-245):

```python
def create_source_use_case(self, session: Session) -> CreateSourceUseCase:
    return CreateSourceUseCase(
        source_repo=SqlaSourceRepository(session),
        subtitle_extractor=self._subtitle_extractor,
        audio_track_lister=self._subtitle_extractor,
        file_reader=self._file_reader,
    )
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/ -v --timeout=30`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/backend/infrastructure/container.py
git commit -m "feat: wire FileReader into DI container"
```

---

### Task 4: API endpoint `POST /sources/file`

**Files:**
- Modify: `backend/src/backend/infrastructure/api/routes/sources.py`
- Create: `backend/src/backend/application/dto/file_source_dtos.py`
- Modify: `backend/tests/integration/test_api_sources.py`

- [ ] **Step 1: Create the request DTO**

```python
# backend/src/backend/application/dto/file_source_dtos.py
from __future__ import annotations

from pydantic import BaseModel


class FileSourceRequest(BaseModel):
    """Input for creating a source from a local file path."""

    file_path: str
    srt_path: str | None = None
    title: str | None = None
    subtitle_track_index: int | None = None
    audio_track_index: int | None = None
```

- [ ] **Step 2: Write the failing integration test**

Add to `backend/tests/integration/test_api_sources.py`:

```python
@pytest.mark.integration
class TestCreateFileSource:
    def test_text_file_creates_source(self, client: TestClient, tmp_path: Path) -> None:
        txt_file = tmp_path / "article.txt"
        txt_file.write_text("Hello world, this is a test article.", encoding="utf-8")

        resp = client.post("/sources/file", json={
            "file_path": str(txt_file),
            "title": "Test Article",
        })

        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["status"] == "new"

    def test_missing_file_returns_404(self, client: TestClient) -> None:
        resp = client.post("/sources/file", json={
            "file_path": "/nonexistent/file.txt",
        })

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/integration/test_api_sources.py::TestCreateFileSource -v`
Expected: FAIL — 404 (endpoint doesn't exist)

- [ ] **Step 4: Implement the endpoint**

In `backend/src/backend/infrastructure/api/routes/sources.py`, add import:

```python
from backend.application.dto.file_source_dtos import FileSourceRequest
```

Add the new endpoint (before the existing `create_video_source`):

```python
@router.post("/file", status_code=201)
def create_file_source(
    request: FileSourceRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    from backend.application.dto.video_dtos import TrackSelectionRequired

    use_case = container.create_source_use_case(session)
    try:
        result = use_case.execute_from_file(
            file_path=request.file_path,
            srt_path=request.srt_path,
            title=request.title,
            subtitle_track_index=request.subtitle_track_index,
            audio_track_index=request.audio_track_index,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if isinstance(result, TrackSelectionRequired):
        return {
            "status": "track_selection_required",
            "file_path": request.file_path,
            "srt_path": request.srt_path,
            "subtitle_tracks": [
                {
                    "index": t.index,
                    "language": t.language,
                    "title": t.title,
                    "codec": t.codec,
                }
                for t in result.subtitle_tracks
            ],
            "audio_tracks": [
                {
                    "index": t.index,
                    "language": t.language,
                    "title": t.title,
                    "codec": t.codec,
                    "channels": t.channels,
                }
                for t in result.audio_tracks
            ],
        }

    # Both Source and VideoSourceCreated
    source_id = result.source_id if hasattr(result, "source_id") else result.id
    session.commit()
    return {"id": source_id, "status": "new"}
```

- [ ] **Step 5: Run integration tests to verify they pass**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/integration/test_api_sources.py::TestCreateFileSource -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/backend/application/dto/file_source_dtos.py backend/src/backend/infrastructure/api/routes/sources.py backend/tests/integration/test_api_sources.py
git commit -m "feat: add POST /sources/file endpoint"
```

---

### Task 5: Remove old `POST /sources/video` endpoint

**Files:**
- Modify: `backend/src/backend/infrastructure/api/routes/sources.py:291-365`
- Modify: `backend/tests/integration/test_api_sources.py` (remove tests for old endpoint if any)

- [ ] **Step 1: Check for tests referencing `/sources/video`**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && grep -rn "sources/video" backend/tests/`

If tests exist, remove them — the functionality is covered by the new `/sources/file` endpoint.

- [ ] **Step 2: Delete the `create_video_source` endpoint**

In `backend/src/backend/infrastructure/api/routes/sources.py`, remove the entire `create_video_source` function (lines 291-365) and its related imports (`UploadFile`, `File`, `Form`, `uuid`, `os` if no longer needed).

- [ ] **Step 3: Run all backend tests**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/ -v --timeout=30`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/backend/infrastructure/api/routes/sources.py backend/tests/
git commit -m "refactor: remove old POST /sources/video multipart endpoint"
```

---

### Task 6: Frontend — API client changes

**Files:**
- Modify: `frontends/web/src/api/client.ts:214-247`

- [ ] **Step 1: Replace `createVideoSource` with `createFileSource`**

In `frontends/web/src/api/client.ts`, replace the `createVideoSource` method (lines 214-247) with:

```typescript
createFileSource: async (
    filePath: string,
    srtPath: string | undefined,
    title: string | undefined,
    subtitleTrackIndex: number | undefined,
    audioTrackIndex: number | undefined,
  ): Promise<{
    id?: number
    status: string
    subtitle_tracks?: SubtitleTrack[]
    audio_tracks?: AudioTrack[]
    file_path?: string
    srt_path?: string
  }> => {
    const body: Record<string, unknown> = { file_path: filePath }
    if (srtPath) body.srt_path = srtPath
    if (title) body.title = title
    if (subtitleTrackIndex !== undefined) body.subtitle_track_index = subtitleTrackIndex
    if (audioTrackIndex !== undefined) body.audio_track_index = audioTrackIndex
    const res = await fetch(`${BASE}/sources/file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => null)
      throw new Error(err?.detail ?? res.statusText)
    }
    return res.json()
  },
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload/frontends/web && npm run build`
Expected: Compilation errors in InboxPage.tsx — `createVideoSource` no longer exists. This is expected and will be fixed in Task 7.

- [ ] **Step 3: Commit**

```bash
git add frontends/web/src/api/client.ts
git commit -m "feat: replace createVideoSource with createFileSource in API client"
```

---

### Task 7: Frontend — InboxPage File tab redesign

**Files:**
- Modify: `frontends/web/src/pages/InboxPage.tsx`

This is the largest frontend change. Replace the drag-and-drop/file picker UI with text inputs for file paths.

- [ ] **Step 1: Replace state variables**

In `InboxPage.tsx`, replace these state variables (around lines 73, 82-83):

Remove:
```typescript
const [files, setFiles] = useState<File[]>([])
const [pendingVideoFile, setPendingVideoFile] = useState<File | null>(null)
const [pendingSrtFile, setPendingSrtFile] = useState<File | null>(null)
```

Add:
```typescript
const [filePath, setFilePath] = useState('')
const [srtPath, setSrtPath] = useState('')
const [pendingFilePath, setPendingFilePath] = useState('')
const [pendingSrtPath, setPendingSrtPath] = useState('')
```

- [ ] **Step 2: Replace `detectedFileType` function**

Replace the function at lines 10-20:

```typescript
function detectedFileType(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'epub') return 'Book · epub'
  if (['mp4', 'mkv', 'avi', 'mov'].includes(ext)) return 'Video · ' + ext
  if (ext === 'srt') return 'Subtitles · srt'
  if (ext === 'html') return 'Article · html'
  return 'Text · ' + (ext || 'txt')
}

function isVideoPath(path: string): boolean {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  return ['mp4', 'mkv', 'avi', 'mov'].includes(ext)
}
```

- [ ] **Step 3: Replace handleAdd for file tab**

Replace the file tab handling in `handleAdd` (around lines 150-189):

```typescript
// File tab — send path to backend
if (activeTab === 'file') {
  if (!filePath.trim()) {
    setError('Enter file path')
    return
  }
  setAdding(true)
  try {
    const result = await api.createFileSource(
      filePath.trim(),
      srtPath.trim() || undefined,
      title.trim() || undefined,
      undefined,
      undefined,
    )
    if (result.status === 'track_selection_required') {
      setPendingFilePath(result.file_path ?? filePath.trim())
      setPendingSrtPath(result.srt_path ?? srtPath.trim())
      setSubtitleTracks(result.subtitle_tracks ?? [])
      setAudioTracks(result.audio_tracks ?? [])
      setSelectedSubtitleIndex(result.subtitle_tracks?.[0]?.index ?? null)
      setSelectedAudioIndex(result.audio_tracks?.[0]?.index ?? null)
      setShowTrackModal(true)
    } else if (result.id) {
      setFilePath('')
      setSrtPath('')
      setTitle('')
      await reloadSources()
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    setError(msg)
  } finally {
    setAdding(false)
  }
  return
}
```

- [ ] **Step 4: Replace handleConfirmTracks**

Replace `handleConfirmTracks` (around lines 302-331):

```typescript
const handleConfirmTracks = async () => {
  if (!pendingFilePath) return
  if (subtitleTracks.length > 0 && selectedSubtitleIndex === null) return
  if (audioTracks.length > 0 && selectedAudioIndex === null) return
  setShowTrackModal(false)
  setAdding(true)
  try {
    const result = await api.createFileSource(
      pendingFilePath,
      pendingSrtPath || undefined,
      title.trim() || undefined,
      subtitleTracks.length > 0 ? selectedSubtitleIndex ?? undefined : undefined,
      audioTracks.length > 0 ? selectedAudioIndex ?? undefined : undefined,
    )
    if (result.id) {
      setFilePath('')
      setSrtPath('')
      setTitle('')
      setPendingFilePath('')
      setPendingSrtPath('')
      setSubtitleTracks([])
      setAudioTracks([])
      await reloadSources()
    }
  } catch (e: unknown) {
    setToast({ text: e instanceof Error ? e.message : String(e), key: Date.now() })
  } finally {
    setAdding(false)
  }
}
```

- [ ] **Step 5: Remove drag-and-drop handlers**

Remove `handleGlobalDragOver` and `handleGlobalDrop` (around lines 343-352). Remove `onDragOver` and `onDrop` props from JSX elements that reference them.

- [ ] **Step 6: Replace File tab UI (JSX)**

Replace the File tab content (around lines 477-586) with:

```tsx
{activeTab === 'file' && (
  <div className="space-y-3">
    <div>
      <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
        File path
      </label>
      <input
        type="text"
        value={filePath}
        onChange={(e) => { setFilePath(e.target.value); setError(null) }}
        placeholder="/path/to/file.mp4"
        className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-2 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
      />
    </div>
    {filePath.trim() && isVideoPath(filePath.trim()) && (
      <div>
        <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
          Subtitles (.srt) — optional
        </label>
        <input
          type="text"
          value={srtPath}
          onChange={(e) => setSrtPath(e.target.value)}
          placeholder="/path/to/subtitles.srt"
          className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-2 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
        />
      </div>
    )}
    {filePath.trim() && (
      <div className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
        <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-accent)]" />
        {detectedFileType(filePath.trim())}
      </div>
    )}
  </div>
)}
```

- [ ] **Step 7: Remove unused imports**

Remove `Upload` from lucide-react imports (line 3) if no longer used. Remove any other unused imports related to File objects.

- [ ] **Step 8: Verify TypeScript compiles**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload/frontends/web && npm run build`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add frontends/web/src/pages/InboxPage.tsx
git commit -m "feat: replace file upload with file path input in InboxPage"
```

---

### Task 8: Run full test suite and verify

**Files:** none (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/python -m pytest backend/tests/ -v --timeout=30`
Expected: PASS

- [ ] **Step 2: Run linter**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/ruff check .`
Expected: PASS

- [ ] **Step 3: Run type checker**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && .venv/bin/mypy backend/src`
Expected: PASS

- [ ] **Step 4: Run frontend build**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload/frontends/web && npm run build`
Expected: PASS

- [ ] **Step 5: Start dev server and test manually**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki/.claude/worktrees/file-path-instead-of-upload && make up-worktree`

Manual test checklist:
1. Open InboxPage → File tab shows text input, not drag-and-drop
2. Enter path to a .txt file → badge shows "Text · txt" → Add → source created
3. Enter path to a .srt file → badge shows "Subtitles · srt" → Add → source created
4. Enter path to a .mkv file → srt field appears → Add without srt → tracks extracted or error
5. Enter path to a .mp4 file + .srt path → Add → source created with subtitles
6. Enter nonexistent path → Add → error message shown
7. URL tab still works (YouTube URL)
8. Text tab still works (paste text)
