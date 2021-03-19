---
title: flashzettl
id: 20210210112545
keywords:
  - zettlr
  - zettelkasten
  - tools
---
# flashzettl
Python script to create anki flashcards from markdown notes.

[genanki](https://github.com/kerrickstaley/genankihttps://github.com/kerrickstaley/genanki) is used to generate the Anki cards/decks and [markdown for python](https://github.com/Python-Markdown/markdown) converts the markdown to html.
    
Cards anywhere in the text can be started with `#anki`. The next two paragraphs will be interpreted as front and back of the card:

```
#anki
front
can span mutliple lines
- and may contain lists
- or even images

back
also spans multiple lines
needs to end with an empty line or the end of the file
```

After a card has been exported `#anki` is replaced with `#_anki`

The deck can be specified with `#anki=deck` and may be of the form `deck::subdeck::subdeck` or `deck:subdeck:subdeck` to avoid the highlight that some markdown editors display for double colons. The deck can also be specified for all cards in a file by adding the keyword `_anki=deck` in the YAML-frontmatter like so:

```
---
title: ...
keywords:
  - _anki=deck
---
```
In this case, the per-card specified deck may still override the file-wide deck.

# known issues
- so far Markdown tables, mermaid diagrams, and codeblocks are not fully supported
- a card cannot be added to several decks in one go
- since paragraphs are used to delimit the card fields, the card's front and back have to be a single paragraph, a list, or a paragraph followed by a list

# under the hood
This is the regex that matches cards:

``(?<![0-9a-zA-Z`>\S])#anki[=]?(.*)*\n([\s\S\]+?(?=\n*\n))\n*\n([\s\S]+?(?=\n*\n|\Z))``

- contains 3 capture groups for the _deck name_, _front_, and _back_
- the `#anki` tag may not be preceded by text, a whitespace, backticks or angle brackets through the negative lookbehind ``(?<![0-9a-zA-Z`>\S])``
- deck-names are optional through `[=]?(.*)`
- might include trailing whitespaces in the deck name
- collects the question via `([\s\S]+?(?=\n *\n|\Z))` to match anything (including line breaks) until two consecutive line breaks or the EOF are reached
- can deal with spaces in the empty line separating the question and answer
- doesn't include the consecutive line breaks in the capture groups
- `([\s\S]+?(?=\n *\n|\z))` does the same but may also be terminated by the end-of-file character `\z`

