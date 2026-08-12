# FrostBook

FrostBook is a local, browser-based experiment logbook built with Python and MkDocs Material.

It generates a searchable notebook from experiment folders in Orchid structure:

```text
data/
└── <date>/
    └── <fridge>/
        └── <exp_id>/
            ├── metadata.yaml
            ├── procedure.yaml
            ├── notes.md
            ├── summary.txt
            └── <images>
```

`data/` is expected to live on shared or synced storage, such as a NAS.

The FrostBook **generator is strictly read-only over source data**. An optional local browser editor can explicitly modify `notes.md`, add images, or delete images when requested by the user. Experiments can be protected from browser edits with `.frostbook-lock`.

Each user can point FrostBook at their own local copy or mount of the same data and build the notebook independently.

## Setup

From the FrostBook repository root:

```bash
python3 -m pip install -e .
```

This installs FrostBook and its dependencies in editable mode.

The package source lives under:

```text
src/frostbook/
```

## Usage

### Generate the full notebook

From the repository root:

```bash
python3 -m frostbook --data-dir data
```

A full build recreates the generated `docs/` directory from the source data.

### Browse locally

```bash
mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000/
```

### Enable browser editing

In a second Terminal:

```bash
python3 -m frostbook.editor --data-dir data --docs-dir docs
```

The editor API runs locally on port `8765`; continue browsing FrostBook through MkDocs on port `8000`.

When the editor is running, experiment pages can:

* edit and save `notes.md`
* upload PNG/JPG/JPEG plots or images
* delete existing experiment images
* automatically rerender the affected experiment after a change

## Incremental updates

FrostBook can update only the part of the notebook that changed instead of rescanning the full dataset.

Update one experiment:

```bash
python3 -m frostbook --update data/2026-08-05/zpc/0001
```

Update from a file inside an experiment:

```bash
python3 -m frostbook --update data/2026-08-05/zpc/0001/notes.md
```

Update one fridge:

```bash
python3 -m frostbook --update data/2026-08-05/zpc
```

Update one complete date:

```bash
python3 -m frostbook --update data/2026-08-05
```

Incremental updates use `.frostbook-manifest.json` as a lightweight local cache so indexes, tags, and related-experiment links can be refreshed without rereading the entire dataset.

Browser edits automatically trigger an incremental update for the edited experiment.

## How it works

* Each experiment gets its own page, identified by its full `date/fridge/exp_id` path because experiment IDs such as `0001` can repeat.
* `metadata.yaml` is displayed as formatted tables together with its raw YAML.
* `procedure.yaml` is summarized into useful fields and sweep information, with the raw YAML also available.
* `summary.txt` is optional. When present, it appears as a collapsible **Summary** section.
* `notes.md` is displayed directly on the experiment page and can optionally be edited through the browser.
* Supported plots/images are discovered automatically and copied into the generated `docs/assets/` tree.
* Images can optionally be uploaded or deleted through the browser editor.
* The homepage shows recent experiments and date/fridge sessions.
* Tags appear throughout the notebook and have a dedicated Tags page.
* Experiments sharing enough tags can display up to three **Related Experiments**.
* A browser-accessible **Help** page contains common FrostBook commands and workflow information.

Generated files in `docs/` should not be edited manually because they may be overwritten by FrostBook.

## Browser edit locks

Browser editing can be disabled for individual experiments with an optional file:

```text
data/<date>/<fridge>/<exp_id>/.frostbook-lock
```

To prevent notes from being edited:

```text
notes
```

To prevent image uploads and deletions:

```text
images
```

To disable all browser editing:

```text
all
```

Multiple entries and comments are also supported:

```text
# finalized experiment
notes
images
```

Locks are enforced by the editor server, not only by the browser interface.

Deleting `.frostbook-lock` restores normal browser editing.

## Tags

FrostBook derives tags automatically from experiment information including:

* sample
* fridge
* cooldown
* procedure
* topic

A useful or high-quality experiment can also be manually marked with the special `star` tag in `metadata.yaml`:

```yaml
tags:
  - star
```

`star` appears as its own section on the Tags page and does not contribute to Related Experiment similarity.

## Skipping data

`skip.txt` files can hide data from FrostBook without deleting or modifying the original experiment data.

Skip dates:

```text
data/skip.txt
```

Skip fridges within a date:

```text
data/<date>/skip.txt
```

Skip experiments within a fridge:

```text
data/<date>/<fridge>/skip.txt
```

Entries can be separated by spaces, commas, or new lines. Anything after `#` is treated as a comment.

For example:

```text
0001
0004

# bad cooldown
0012
```

## Project structure

```text
frostbook/
├── src/
│   └── frostbook/
│       ├── __init__.py
│       ├── __main__.py
│       ├── generate_logbook.py
│       ├── editor.py
│       └── resources/
│           ├── extra.css
│           ├── extra.js
│           ├── help.md
│           └── overrides/
├── data/                  # local/shared source data; not committed
├── docs/                  # generated MkDocs source; not committed
├── site/                  # generated static site; not committed
├── mkdocs.yml
├── pyproject.toml
├── README.md
└── .gitignore
```

`data/`, `docs/`, `site/`, and `.frostbook-manifest.json` are local or generated state and should normally remain gitignored.

## Suggested workflow

1. Mount or sync the experiment `data/` directory.
2. Install FrostBook with `python3 -m pip install -e .`.
3. Run one full FrostBook build.
4. Run `mkdocs serve` to browse the notebook.
5. Run `frostbook-editor` if browser editing is needed.
6. Use browser controls for notes and images, or `--update` for other source-data changes.
7. Use a full build whenever the complete notebook should be regenerated.
