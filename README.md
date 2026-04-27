# French Flashcards

A flashcard web app for vocabulary encountered while reading French books. Each card shows a French word with French + English definitions, CEFR level (B1–C2), the chapter and page where it first appeared, and — for verbs — a full conjugation table.

Live: [nathanschulz.github.io/french-flashcards](https://nathanschulz.github.io/french-flashcards/)

## How it works

The card data (`cards.js`) is generated from chapter-by-chapter Markdown vocab files produced by a separate pipeline ([`french-vocab-tool`](https://github.com/nathanschulz/french-vocab-tool)). When new chapters are added, regenerate `cards.js` and push.

Filter by text → chapter → CEFR level. The next-card picker weights toward words you've gotten wrong. Stats and filter prefs persist in `localStorage`.

## Adding a new chapter or text

1. Process the chapter through `french-vocab-tool` to produce a `chN.md`, then drop it into this repo's `chapters/` directory.
2. Add the file path to [`texts.json`](./texts.json):
    ```json
    [
      {
        "id": "fanon-pnmb",
        "name": "Peau noire, masques blancs",
        "author": "Frantz Fanon",
        "shortName": "Fanon",
        "files": ["chapters/ch1.md", "chapters/ch2.md"]
      }
    ]
    ```
3. `python3 make_flashcards.py` to regenerate `cards.js` (stdlib only — no deps).
4. Commit and push. The Pages deployment refreshes automatically.

## Install on iPhone

Open the URL in Safari, tap **Share → Add to Home Screen**.

## Source data

Definitions: French and English Wiktionary (CC BY-SA 4.0). CEFR levels: [FLELex](https://cental.uclouvain.be/cefrlex/flelex/) (CC BY-NC-SA 4.0). Verb conjugations: [`mlconjug3`](https://github.com/Ars-Linguistica/mlconjug3) (MIT).

## License

MIT for the app code. Card data inherits the licenses of the source dictionaries above.
