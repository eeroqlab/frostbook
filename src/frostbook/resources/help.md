# FrostBook Help

Quick reference for building, updating, editing, and managing FrostBook.

---

## Running FrostBook

### Generate everything

Rebuild FrostBook from the full data directory:

```bash
python3 -m frostbook --data-dir data
```

or:

```bash
frostbook --data-dir data
```

A full build recreates the generated `docs/` directory.

### Start the browser

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
frostbook-editor --data-dir data --docs-dir docs
```

or:

```bash
python3 -m frostbook.editor --data-dir data --docs-dir docs
```

The editor runs locally on port `8765`. Continue browsing FrostBook through the normal MkDocs page on port `8000`.

A convenient setup is:

```text
Terminal 1 → mkdocs serve
Terminal 2 → frostbook-editor
```

---

## Browser editing

When the editor server is running, experiment pages can modify selected source files directly.

### Edit notes

Click **Edit Notes** underneath the Notes section.

Changes are saved to:

```text
data/DATE/FRIDGE/EXPERIMENT/notes.md
```

Saving automatically updates that experiment in FrostBook.

### Add a plot, image, or PDF

Click:

```text
+ Add Plot / Image / PDF
```

Supported uploads:

```text
.png
.jpg
.jpeg
.pdf
```

The image is saved directly inside the experiment folder and the page is automatically updated.

If the filename already exists, FrostBook creates a new filename such as:

```text
plot_2.png
```

instead of overwriting the original.

### Delete a plot, image, or PDF

Each displayed file has a **Delete image** control.

FrostBook asks for confirmation before permanently deleting the source file from the experiment folder.

The experiment page is automatically rebuilt afterward.

---

## Locking browser edits

Create:

```text
data/DATE/FRIDGE/EXPERIMENT/.frostbook-lock
```

to prevent browser editing for an experiment.

Lock notes:

```text
notes
```

Lock image uploads and deletions:

```text
images
```

Lock everything:

```text
all
```

Multiple entries and comments are allowed:

```text
# finalized experiment
notes
images
```

Delete `.frostbook-lock` to restore normal browser editing.

Locks are enforced by the editor server, not only by the browser buttons.

---

## Updating data manually

Use `--update` when source files were changed outside the browser editor.

### Update one experiment

```bash
python3 -m frostbook --update data/2026-08-05/zpc/0001
```

You can also point directly to a file inside the experiment:

```bash
python3 -m frostbook --update data/2026-08-05/zpc/0001/notes.md
```

### Update one fridge

```bash
python3 -m frostbook --update data/2026-08-05/zpc
```

### Update one date

```bash
python3 -m frostbook --update data/2026-08-05
```

Browser edits trigger their own experiment update automatically, so these commands are mainly needed for changes made directly in `data/`.

---

## Skipping data

FrostBook uses `skip.txt` files to exclude data from the rendered notebook without deleting the original experiment data.

### Skip whole dates

Create:

```text
data/skip.txt
```

Example:

```text
2026-08-04
2026-08-07
```

### Skip a fridge on one date

Create:

```text
data/2026-08-05/skip.txt
```

Example:

```text
zpc
```

### Skip individual experiments

Create:

```text
data/2026-08-05/zpc/skip.txt
```

Example:

```text
0001
0003
0015
```

Entries can be separated by spaces, commas, or new lines.

Anything after `#` is treated as a comment.

---

## Starring experiments

To mark a useful or high-quality experiment, add `star` to the `tags` field in `metadata.yaml`:

```yaml
tags:
  - star
```

If other tags already exist:

```yaml
tags:
  - calibration
  - star
```

The experiment appears in the **star** section of the Tags page.

After editing metadata manually, update that experiment:

```bash
python3 -m frostbook --update data/DATE/FRIDGE/EXPERIMENT
```

The `star` tag does not count toward Related Experiment similarity.

---

## summary.txt

An experiment may optionally contain:

```text
summary.txt
```

When present, FrostBook displays it in a **Summary** dropdown.

If the file does not exist, no Summary dropdown is shown.

---

## Related Experiments

FrostBook can show up to three related experiments at the bottom of an experiment page.

Experiments must share at least three similarity tags to qualify.

Matches with more shared tags rank first. Ties prefer newer experiments.

The `star` tag is ignored when calculating similarity.

---

## Important

`data/` is the permanent source of experiment data.

The generator reads from `data/` but never modifies it.

The optional browser editor can intentionally modify:

```text
notes.md
images
```

when the user saves, uploads, or deletes content.

`docs/` and `site/` are generated FrostBook output and may be recreated during a full build. Do not manually edit generated files there.
