# Recent

## Principle

The sources screen opens on **Recent**: the collections and sources the user worked with,
the latest first. It sits above All and Unsorted in the tree. Its order is fixed by its
meaning, so the shared Group/Sort choice does not apply to it; All, Unsorted and the
collections keep that one shared choice.

## What counts as working with an item

A **use** is a moment the user worked with a source or a collection:

| Action | Item used |
|---|---|
| Add one source (text, file, link, topic) | that source |
| Add several sources into a collection (a book split into chapters) | that collection |
| Add several sources without a collection | each of them |
| Open the review of a collection or a source | that collection or source |
| Any change on an open review: a decision, its undo, an added or replaced word, an edit of a card | the review's collection or source |
| Save a phrase (extension, Quick Add) | Saved phrases |

Opening a collection in the tree, opening All or Unsorted, and reviewing All are not uses.
Recording a use is a timestamp, not work: nothing is processed or generated.

## Entities and ports

- `RecentUse` (value object): `scope: SourceScope` (a source or a collection), `used_at`.
- `RecentUseRepository` (port): `mark(scopes, at)` keeps the latest moment per item;
  `list_all()` gives every recorded use.
- Storage: table `recent_uses` — one row per item, `source_id` or `collection_id`
  (cascade on delete), `used_at`. A soft-deleted collection is left out when read.

## Use cases

- `SourceGroupWriter` marks what an add made (table above); `CreateTopicUseCase` marks the
  topic.
- `OpenReviewUseCase` marks a collection or source scope.
- `ReviewMutation` marks the review's scope after every change it runs: in a collection's
  review the collection rises, not the chapter the card came from.
- `AddSavedPhraseUseCase` marks the Saved phrases source.
- `GetRecentUseCase.board(query)` → `RecentBoardDTO.items`, latest first. Each item is a
  source (the same `SourceDTO` the lists show) or a collection (the same
  `CollectionNodeDTO` the tree shows, plus the names of its ancestors). `query` filters by
  title or name. API: `GET /api/sources/recent?query=`.
- `GetRecentUseCase` reads the rows through `GetSourcesUseCase.summaries` and the nodes
  through `ListCollectionsUseCase`, so they match the lists and the tree.

## Migration (0072)

Creates `recent_uses` and fills it from what is known:

- a source outside collections: the later of its adding and its last marked card;
- a collection: the latest of the same moments over the sources directly in it.

Sources inside a collection get no row: their collection stands for them.

## UI

- Tree: `Recent` (clock icon) above All and Unsorted, no counter.
- The screen opens on Recent when the address names no scope; All gets `?scope=all`.
- Recent's header: the title only — no Group/Sort menu, no Review/Export of the whole list.
- A source row is the usual source row. A collection row looks like a source row: folder
  icon, name, its parent collection, the collection's progress and caption, Review action,
  the collection's menu. A click on it opens its review.
- Search filters Recent like any scope.
