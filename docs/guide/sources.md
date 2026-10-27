# Sources

A **source** is anything you want to learn words from: an article, a book, a song, subtitles, a video file or a YouTube video. Everything starts on the **Sources** screen, which is the app's home page.

![Sources screen](../images/sources.png)

## What you can add

| Input | How it is recognised | Notes |
|---|---|---|
| Pasted text | Anything that is not a link or a path | The app asks **Is it a text or a song?** |
| Markdown file | `.md`, `.markdown` | Markup is dropped, headings and lists are kept |
| HTML file or pasted HTML | `.html`, `.htm`, or HTML tags in pasted text | Headings, paragraphs and list items are kept |
| Plain text file | Any other extension, e.g. `.txt` | UTF-8, UTF-16 with BOM, or Windows-1252 |
| Subtitles | `.srt` file, or pasted SRT text | Rolling YouTube-style captions are de-duplicated |
| Video file | `.mp4`, `.mkv`, `.avi`, `.mov` | Needs subtitles: an attached `.srt` or an embedded text track |
| YouTube link | `youtube.com`, `m.youtube.com`, `youtu.be` | Needs English subtitles (auto-generated ones are fine) |
| EPUB book | `.epub` | Can be split into one source per chapter |

Other links (web articles, other video sites) are not supported. Paste the article's text, or save it as a file and add the file.

PDF, FB2, `.webm`, `.vtt` and `.ass` files are not supported.

### Text or song

Plain, Markdown and HTML input asks **Is it a text or a song?**

- **Text** is split into sentences across lines.
- **Song** keeps every line as a line, and blank lines separate stanzas. The source shows up as **Lyrics**.

### Cleaning

Every input is cleaned before it is analysed. The app removes:

- timecodes like `[00:01:23]`;
- tags like `[Music]`, `[Applause]`, `[Chorus]`, `[Verse 1]`;
- music symbols;
- repeated lines.

Slang is spelled out, so `wanna` becomes `want to`.

### Videos

A video file stays where it is. The app stores only its path, so do not move or delete the file until you have made the cards. Without the file, the app can't cut screenshots or audio clips from it.

The app takes subtitles from one of two places:

- **An attached `.srt` file.** When you enter a video, a second field for its `.srt` appears.
- **A subtitle track inside the video.** It is read with `ffmpeg`. If the video has several subtitle or audio tracks, the app asks which one to use. Image-based subtitle tracks (PGS, VobSub) can't be read; attach an `.srt` instead.

For a **YouTube** video, only the subtitles are downloaded when you add it. The video itself is downloaded later, when you ask for screenshots and clips (see [Generating card content](review.md#generating-card-content)). It is downloaded at up to 1080p and deleted automatically once every card has its screenshot.

### Books

An EPUB is split by its table of contents. Front matter is skipped: copyright pages, very short chapters and short parts before the contents.

A book with two or more chapters asks how to add it:

- **N chapters**: one source per chapter. Best for long books.
- **One source**: the whole book as one source.

## Ways to add

### The Add box

Type or paste into the **Add** box in the top left. The app recognises the input and shows what it will become, for example `Text · markdown`, `Book · epub` or `Video · YouTube`.

1. Paste text, a YouTube link, or the full path to a file (for example `/Users/me/Books/dune.epub`). The path may be in quotes or start with `~`.
2. Optionally fill in **Title**. Without a title, a file uses its file name, and pasted text uses its first 100 characters.
3. Press **Add source**.
4. Answer the questions, if the app asks any.

The Add box also creates **topics** and saves single **phrases**. The app suggests one of three modes, and you can switch it with the **Source / Topic / Phrase** control:

| Mode | When it is suggested | What it does |
|---|---|---|
| **Source** | Long text, several lines, a link or a file | Adds a source |
| **Topic** | A short query, or text in a language other than English | Creates a [topic](#topics) |
| **Phrase** | One English sentence | Saves the phrase; you tap the words you want to learn |

### Drag and drop, and Choose file

In the [macOS app](macos-app.md), you can drop files anywhere on the window, or use **Choose file…** in the Add box. In a regular browser, type or paste the file's path instead: the browser can't hand dropped files to the app.

Dropping a video together with its `.srt` attaches the subtitles to the video.

### Several files at once

Drop several files, pick several in **Choose file…**, or paste several paths, one per line. The box shows `N files`.

- All files are read first. If one of them can't be read, **nothing is added**, and the error names the file.
- A question that applies to several files (such as text or song) is asked once.
- A naming window opens before the sources are created (see below).

### Naming several sources

When one add makes several sources (a split book or several files), a naming window opens:

- **Collection**: where the new sources go. For a book, it defaults to a collection named after the book. Leave it empty to put the sources in **Unsorted**.
- **Name them**: a naming rule built from **+ Collection**, **+ Number**, **+ Title from file** and free text. The rule must include the number or the title. The default rule is `{{collection}} ch{{n}}`; change it in **Settings → Books**.
- **Numbers**: **Auto**, `1`, `01` or `001`. Auto pads numbers so titles sort correctly.
- A preview shows every title. You can overwrite any of them by hand.

### Quick Add from any app

In the macOS app, you can save a phrase from any other app. See [Quick Add](macos-app.md#quick-add).

## Processing

**Adding a source does not process it.** A new source shows **Not processed yet** and a **Process** button. Processing:

- splits the text into phrases;
- picks the words, phrasal verbs and collocations that are new to you;
- lays out the cards.

You can process sources in three ways:

- **Process** on one source;
- **Process** in the selection bar, for the selected sources;
- **Process all (N)** at the top of the list, for every unprocessed source in the open collection.

Processing does not use AI. An article takes a few seconds; a whole book takes longer.

### The progress overlay

Processing, and a few other large operations, block the whole app with an overlay. The overlay shows a percentage and a **Cancel** button.

- **Cancel** rolls everything back, as if the operation never started.
- Only one such operation runs at a time.

The other operations that use the overlay are **Find words again**, **Process again**, **Refresh** and a level change.

If processing fails, the source shows **Processing failed** and a **Retry** button. The details are in the logs (`make logs`).

### Source status

With grouping by status on, the list is split into groups:

| Group | Meaning |
|---|---|
| **In progress** | Processed, and some cards are decided |
| **Preparing** | Not processed yet, failed, or a topic waiting for AI |
| **Ready to review** | Processed, nothing decided yet |
| **Reviewed** | Every card is decided |

Each source has one main button: **Process**, **Retry**, **Review**, **Continue** or **Open**. Clicking a processed source opens its [review](review.md).

## Topics

A **topic** is a source made from a request instead of a text, for example `phrasal verbs with get` or `words for talking about money`. You can type the request in any language.

1. Type the request in the Add box, choose **Topic**, and press **Add topic**.
2. Press **Generate** on the topic. AI proposes 20 words for your level, each with an example sentence.
3. Press **Process**. For each word, the app looks for a real phrase in your other sources. Only if none is found does it use the AI example.

Later, **Refresh…** in the topic's menu looks for its words in sources you added since. It only adds new phrases; your decisions and cards stay as they are.

## Collections

Collections are folders for sources. They can be nested up to 5 levels deep.

- **All** shows every source. **Unsorted** shows sources that are in no collection.
- Create a collection with **+** next to **Collections**, or with **New subcollection** in a collection's menu.
- Rename a collection by double-clicking it, pressing **F2**, or choosing **Rename** in its menu.
- Drag a collection to reorder it or to put it inside another one.
- **Add to favorites** pins a collection at the top of the tree.
- A collection includes its subcollections. Review, export and **Process all** cover all of them.

Deleting a collection does not delete its sources: they move to the parent collection, or to **Unsorted**. An **Undo** button appears right after the delete.

Names must be unique among siblings (case-insensitive) and at most 200 characters long.

## Managing sources

Open a source's **…** menu for these actions:

| Action | What it does |
|---|---|
| **Export** | Opens [export to Anki](anki-export.md) for this source. Shown once you have words to learn |
| **Rename** | Renames the source. Double-clicking the title does the same |
| **Move to…** | Moves the source to another collection. On desktop you can also drag it onto the tree |
| **Find words again…** | Looks for words to learn again, using your current known words, level and rules. Keeps the phrases of your cards with their polish, meaning and audio |
| **Process again…** | Splits the text into phrases again, as when you added it. Decisions stay. A card whose phrase changes loses its polish and audio |
| **Refresh…** | For topics: adds phrases from sources added since |
| **Delete** | Deletes the source, its cards and its media. This can't be undone |

**Find words again**, **Process again** and **Refresh** first show a preview of what will change. Nothing happens until you confirm.

The same operations are available for a whole collection, for **Unsorted** and for **All** in their menus.

### Selecting several sources

- ⌘-click toggles a source.
- Shift-click selects a range.
- ⌘A selects every visible source.
- Esc clears the selection.

The selection bar offers **Move to…**, **Process** and **Delete**.

### Search, group and sort

- The search box filters the open collection by title.
- The **…** menu at the top of the list has **Group** (**By status** or **None**) and **Sort** (**Date added**, **Name** or **Last studied**). The choice applies to every collection.

## Saved phrases

**Saved phrases** is a built-in source that collects single phrases you saved with the **Phrase** mode or with [Quick Add](macos-app.md#quick-add). The words you pick there are marked **Learn** right away. Saved phrases can't be deleted.
