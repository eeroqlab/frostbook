#!/usr/bin/env python3
"""
generate_logbook.py

Scans data/<date>/<fridge>/<exp_id>/ for
{metadata.yaml, procedure.yaml, notes.md, <images>},
and (re)generates a MkDocs-ready markdown logbook in docs/.

This script is strictly read-only over data/ — it never creates or
modifies anything there. data/ is expected to be a shared/synced folder
(e.g. from a NAS), so every user can point this generator at their own
local copy and build their own logbook independently.

Usage:
    python generate_logbook.py
    python generate_logbook.py --data-dir data --docs-dir docs
"""

import argparse
import hashlib
import os
import shutil
import html
import json
from urllib.parse import quote
from pathlib import Path

import yaml

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".pdf")

MANIFEST_FILENAME = ".frostbook-manifest.json"

SKIP_FILENAME = "skip.txt"

RESOURCE_DIR = (
    Path(__file__).parent
    / "resources"
)

NO_NOTES_PLACEHOLDER = "_(no notes yet — add a notes.md in this experiment's folder)_\n"

DATE_EMOJIS = [
    "🐧", "🦊", "🐢", "🐙", "🦄", "🐝", "🦋", "🐳", "🦉", "🐸",
    "🐨", "🐼", "🦁", "🐯", "🐰", "🦔", "🦕", "🐬", "🦩", "🐌",
    "🌸", "🌻", "🌵", "🍀", "🍁", "🍄", "🌈", "⭐", "🌙", "🔥",
    "💧", "❄️", "⚡", "🌊", "🍉", "🍇", "🍒", "🍋", "🥝", "🍍",
    "🥑", "🌽", "🍩", "🍪", "🍔", "🍕", "🎈", "🎲", "🎯", "🎨",
    "🎭", "🎸", "🚀", "🛸", "⛵", "🧊", "🔮", "🧩", "🪁", "🧭",
]


def assign_date_emojis(dates: set[str]) -> dict[str, str]:
    assigned = {}
    used = set()
    for date in sorted(dates):
        idx = int(hashlib.sha256(date.encode()).hexdigest(), 16) % len(DATE_EMOJIS)
        while DATE_EMOJIS[idx] in used:
            idx = (idx + 1) % len(DATE_EMOJIS)
        assigned[date] = DATE_EMOJIS[idx]
        used.add(DATE_EMOJIS[idx])
    return assigned

def get_or_assign_date_emoji(date: str, manifest: dict) -> str:
    """
    Return the existing emoji for a date, or assign one if this is
    a brand-new date being added incrementally.
    """
    date_emojis = manifest["date_emojis"]

    if date in date_emojis:
        return date_emojis[date]

    used = set(date_emojis.values())

    idx = (
        int(hashlib.sha256(date.encode()).hexdigest(), 16)
        % len(DATE_EMOJIS)
    )

    while DATE_EMOJIS[idx] in used:
        idx = (idx + 1) % len(DATE_EMOJIS)

    emoji = DATE_EMOJIS[idx]
    date_emojis[date] = emoji

    return emoji

def find_images(exp_dir: Path) -> list[Path]:
    return sorted(
        p for p in exp_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def extract_tags(meta: dict, proc: dict, fridge: str) -> list[str]:
    tags = []

    # Automatically derived FrostBook tags
    if meta.get("sample"):
        tags.append(f"sample/{meta['sample']}")

    if fridge:
        tags.append(f"fridge/{fridge}")

    if meta.get("cooldown"):
        tags.append(f"cooldown/{meta['cooldown']}")

    if proc.get("name"):
        tags.append(f"procedure/{proc['name']}")

    # Explicit user/Orchid tags
    for t in meta.get("tags") or []:
        t = str(t).strip()

        # "star" is a special FrostBook tag category.
        if t.lower() == "star":
            tags.append("star")
        else:
            tags.append(f"topic/{t}")

    # Remove duplicates while preserving order
    return list(dict.fromkeys(tags))

def build_frontmatter(tags: list[str], date: str) -> str:
    data = {
        "date": date,
        "tags": tags,
    }

    yaml_text = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
    ).strip()

    return f"---\n{yaml_text}\n---\n"

def experiment_key(date: str, fridge: str, exp_id: str) -> str:
    """
    Stable identifier for one experiment.
    """
    return f"{date}/{fridge}/{exp_id}"


def load_manifest(path: Path) -> dict:
    """
    Load FrostBook's cached experiment index.

    The manifest contains only lightweight metadata needed to rebuild
    indexes. It does NOT contain scientific data.
    """
    if not path.exists():
        return {
            "version": 1,
            "date_emojis": {},
            "experiments": {},
            "related": {},
        }

    with open(path) as f:
        data = json.load(f)

    data.setdefault("version", 1)
    data.setdefault("date_emojis", {})
    data.setdefault("experiments", {})
    data.setdefault("related", {})

    return data


def save_manifest(path: Path, manifest: dict) -> None:
    """
    Atomically save the FrostBook manifest.
    """
    temp_path = path.with_suffix(path.suffix + ".tmp")

    temp_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    temp_path.replace(path)


def manifest_rows(manifest: dict) -> list[dict]:
    """
    Return the experiment rows stored in the manifest.
    """
    return list(manifest["experiments"].values())


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def format_cell(value) -> str:
    if isinstance(value, dict) or (isinstance(value, list) and any(isinstance(v, (dict, list)) for v in value)):
        text = yaml.dump(value, default_flow_style=False, sort_keys=False).strip()
        return "<br>".join(line.replace("|", "\\|") for line in text.split("\n"))
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "—"
    if value is None:
        return "—"
    return str(value)


def metadata_table(meta: dict) -> str:
    if not meta:
        return "_No metadata.yaml found._\n"
    rows = {k: v for k, v in meta.items() if k not in ("control", "readout")}
    if not rows:
        return ""
    lines = ["| Field | Value |", "|---|---|"]
    for key, value in rows.items():
        lines.append(f"| {key} | {format_cell(value)} |")
    return "\n".join(lines) + "\n"


def control_table(control: dict) -> str:
    if not control:
        return ""
    lines = ["\n### Control\n", "| Axis | Controllers |", "|---|---|"]
    for axis, controllers in control.items():
        lines.append(f"| {axis} | {format_cell(controllers)} |")
    return "\n".join(lines) + "\n"


def readout_table(readout: dict) -> str:
    if not readout:
        return ""
    lines = [
        "\n### Readout\n",
        "| Readout | Kind | Unit | Shape | Contains |",
        "|---|---|---|---|---|",
    ]
    for name, spec in readout.items():
        spec = spec or {}
        lines.append(
            f"| {name} | {format_cell(spec.get('kind'))} | {format_cell(spec.get('unit'))} | "
            f"{format_cell(spec.get('shape'))} | {format_cell(spec.get('contains'))} |"
        )
    return "\n".join(lines) + "\n"


def procedure_summary(proc: dict) -> str:
    if not proc:
        return "_No procedure.yaml found._\n"

    scalar_fields = ["kind", "name", "ndim", "shape", "total_points", "estimated_duration_s"]
    lines = ["| Field | Value |", "|---|---|"]
    for key in scalar_fields:
        if key in proc:
            lines.append(f"| {key} | {format_cell(proc[key])} |")
    out = "\n".join(lines) + "\n"

    sweeps = proc.get("sweeps") or []
    if sweeps:
        sweep_lines = [
            "\n**Sweeps**\n",
            "| Axis | Controller | Min | Max | N | Unit | Reverse |",
            "|---|---|---|---|---|---|---|",
        ]
        for s in sweeps:
            sweep_lines.append(
                f"| {s.get('axis', '')} | {s.get('controller', '')} | {s.get('min', '')} | "
                f"{s.get('max', '')} | {s.get('n', '')} | {s.get('unit', '')} | {s.get('reverse', '')} |"
            )
        out += "\n".join(sweep_lines) + "\n"
    return out


def collapsible(title: str, body: str, open_by_default: bool = False) -> str:
    marker = "???+" if open_by_default else "???"
    indented = "\n".join(f"    {line}" if line.strip() else "" for line in body.strip("\n").split("\n"))
    return f'\n{marker} note "{title}"\n{indented}\n'


def raw_block(path: Path, label: str) -> str:
    if not path.exists():
        return ""
    raw = path.read_text()
    return collapsible(label, f"```yaml\n{raw}\n```")

def raw_text_block(path: Path, label: str) -> str:
    """
    Render an optional plain-text file inside a collapsible block.

    If the file does not exist, nothing is rendered.
    """
    if not path.exists():
        return ""

    raw = path.read_text()

    return collapsible(
        label,
        f"```text\n{raw}\n```"
    )

def remove_rendered_experiment(
    date: str,
    fridge: str,
    exp_id: str,
    date_label: str,
    docs_dir: Path,
) -> None:
    """
    Remove one previously generated experiment page and its copied assets.

    This only touches generated docs/.
    It never changes the original data/.
    """
    page_path = (
        docs_dir
        / "experiments"
        / date_label
        / fridge
        / f"{exp_id}.md"
    )

    if page_path.exists():
        page_path.unlink()

    asset_dir = (
        docs_dir
        / "assets"
        / date_label
        / fridge
        / exp_id
    )

    if asset_dir.exists():
        shutil.rmtree(asset_dir)

def material_tag_href(tag: str) -> str:
    """
    Link to the FrostBook Tags page and identify the exact
    tag that should automatically expand there.
    """
    return f"/tags/?tag={quote(tag, safe='')}"

def editor_control_html(
    kind: str,
    date: str,
    fridge: str,
    exp_id: str,
) -> str:
    """
    Insert an HTML marker that extra.js turns into
    browser editing controls.
    """

    return (
        f'<div '
        f'class="frost-editor-control '
        f'frost-editor-{kind}" '
        f'data-date="'
        f'{html.escape(str(date), quote=True)}" '
        f'data-fridge="'
        f'{html.escape(str(fridge), quote=True)}" '
        f'data-experiment="'
        f'{html.escape(str(exp_id), quote=True)}">'
        f'</div>'
    )

def editor_image_control_html(
    date: str,
    fridge: str,
    exp_id: str,
    filename: str,
) -> str:
    """
    Insert an HTML marker underneath one experiment image.

    extra.js turns this marker into that image's
    Delete button.
    """

    return (
        f'<div '
        f'class="frost-editor-control '
        f'frost-editor-image-delete" '
        f'data-date="'
        f'{html.escape(str(date), quote=True)}" '
        f'data-fridge="'
        f'{html.escape(str(fridge), quote=True)}" '
        f'data-experiment="'
        f'{html.escape(str(exp_id), quote=True)}" '
        f'data-filename="'
        f'{html.escape(str(filename), quote=True)}">'
        f'</div>'
    )

def build_experiment_page(
    date: str, fridge: str, exp_id: str, exp_dir: Path, docs_dir: Path, date_emoji: str
) -> dict:
    date_label = f"{date}-{date_emoji}"

    meta = load_yaml(exp_dir / "metadata.yaml")
    proc = load_yaml(exp_dir / "procedure.yaml")
    notes_path = exp_dir / "notes.md"
    notes_content = notes_path.read_text() if notes_path.exists() else NO_NOTES_PLACEHOLDER

    exp_docs_dir = docs_dir / "experiments" / date_label / fridge
    exp_docs_dir.mkdir(parents=True, exist_ok=True)

    images = find_images(exp_dir)
    image_rels = []
    if images:
        asset_dir = docs_dir / "assets" / date_label / fridge / exp_id
        asset_dir.mkdir(parents=True, exist_ok=True)
        for img in images:
            dest = asset_dir / img.name
            shutil.copyfile(img, dest)
            image_rels.append((img.name, os.path.relpath(dest, start=exp_docs_dir)))

    tags = extract_tags(meta, proc, fridge)

    page = []

    frontmatter = build_frontmatter(tags, date)
    if frontmatter:
        page.append(frontmatter)

    page.append(f"# {exp_id}\n")
    page.append(f"\n{date} · {fridge}\n")

    page.append(
        "\n## **Plots**\n"
    )

    if image_rels:
        for name, rel in image_rels:
            page.append(
                f"\n![{name}]({rel})\n"
            )

            page.append(
                "\n"
                + editor_image_control_html(
                    date,
                    fridge,
                    exp_id,
                    name,
                )
                + "\n"
            )

    else:
        page.append(
            "\n_No images found in this "
            "experiment folder._\n"
        )

    page.append(
        "\n"
        + editor_control_html(
            "upload",
            date,
            fridge,
            exp_id,
        )
        + "\n"
    )

    page.append(
        "\n---\n\n## **Notes**\n"
    )

    page.append(
        notes_content
    )

    page.append(
        "\n"
        + editor_control_html(
            "notes",
            date,
            fridge,
            exp_id,
        )
        + "\n"
    )

    page.append(
        "\n---\n"
    )

    metadata_body = (
        metadata_table(meta)
        + control_table(meta.get("control"))
        + readout_table(meta.get("readout"))
    )

    page.append(
        collapsible(
            "Metadata",
            metadata_body
        )
    )

    page.append(
        collapsible(
            "Procedure",
            procedure_summary(proc)
        )
    )

    page.append(
        raw_text_block(
            exp_dir / "summary.txt",
            "Summary"
        )
    )

    page.append(
        raw_block(
            exp_dir / "metadata.yaml",
            "Raw metadata.yaml"
        )
    )

    page.append(
        raw_block(
            exp_dir / "procedure.yaml",
            "Raw procedure.yaml"
        )
    )

    (exp_docs_dir / f"{exp_id}.md").write_text("\n".join(page))

    return {
        "date": date,
        "date_label": date_label,
        "fridge": fridge,
        "id": exp_id,
        "description": meta.get("description", ""),
        "tags": tags,
    }


RECENT_LIMIT = 6

RELATED_LIMIT = 3

# An experiment must share at least this many tags
# to count as related.
RELATED_MIN_SHARED_TAGS = 3

# By default, every tag category counts.
#
# If it is later decided that simply being on the same fridge
# should not count toward similarity, change this to:
#
# RELATED_IGNORE_PREFIXES = ("fridge/",)
RELATED_IGNORE_PREFIXES = ("star",)

RELATED_START = "<!-- FROSTBOOK_RELATED_START -->"
RELATED_END = "<!-- FROSTBOOK_RELATED_END -->"


def group_by_day(rows: list[dict]) -> dict:
    groups = {}
    for r in sorted(rows, key=lambda r: (str(r["date"]), r["fridge"], r["id"]), reverse=True):
        groups.setdefault((r["date"], r["fridge"]), []).append(r)
    return groups

TAG_CATEGORIES = {
    "sample",
    "fridge",
    "procedure",
    "cooldown",
    "topic",
    "star",
}


def tag_display_parts(tag: str) -> tuple[str, str]:
    """
    Turn:
        procedure/stdoor_sweep

    into:
        ("procedure", "stdoor_sweep")
    """
    if "/" in tag:
        category, label = tag.split("/", 1)

    elif tag.lower() == "star":
        category, label = "star", "star"

    else:
        category, label = "other", tag

    category = category.lower()

    if category not in TAG_CATEGORIES:
        category = "other"

    return category, label


def tag_pills_html(tags: list[str]) -> str:
    if not tags:
        return ""

    pills = []

    for tag in tags:
        category, label = tag_display_parts(tag)

        href = material_tag_href(tag)

        pills.append(
            f'<a '
            f'class="frost-table-tag frost-tag--{category}" '
            f'href="{href}">'
            f'{html.escape(label)}'
            f'</a>'
        )

    return (
        '<span class="frost-table-tags">'
        + "".join(pills)
        + "</span>"
    )

def build_index(rows: list[dict], docs_dir: Path) -> None:
    rows_sorted = sorted(rows, key=lambda r: (str(r["date"]), r["fridge"], r["id"]), reverse=True)
    groups = group_by_day(rows)

    lines = [
        '<h1 class="frostbook-logo">FrostBook</h1>\n',
        f"_{len(rows_sorted)} experiments across {len(groups)} date/fridge sessions._\n",
        "\n## Recent\n",
        "| Date | Fridge | Experiment | Description |",
        "|---|---|---|---|",
    ]
    for r in rows_sorted[:RECENT_LIMIT]:
        link = f"experiments/{r['date_label']}/{r['fridge']}/{r['id']}.md"

        description = str(r["description"] or "").replace("|", "\\|")
        tags_html = tag_pills_html(r["tags"])

        if description and tags_html:
            description_cell = f"{description}<br>{tags_html}"
        elif tags_html:
            description_cell = tags_html
        else:
            description_cell = description

        lines.append(
            f"| {r['date']} | {r['fridge']} | "
            f"[{r['id']}]({link}) | {description_cell} |"
        )

    lines.append("\n## By Day\n")
    lines.append("| Date | Fridge | Count |")
    lines.append("|---|---|---|")
    for (date, fridge), group_rows in groups.items():
        link = f"experiments/{group_rows[0]['date_label']}/{fridge}/index.md"
        lines.append(f"| {date} | {fridge} | [{len(group_rows)}]({link}) |")

    (docs_dir / "index.md").write_text("\n".join(lines) + "\n")


def build_day_indexes(rows: list[dict], docs_dir: Path) -> None:
    for (date, fridge), group_rows in group_by_day(rows).items():
        lines = [
            f"# {date} / {fridge}\n",
            f"_{len(group_rows)} experiment{'s' if len(group_rows) != 1 else ''}._\n",
            "| Experiment | Description |",
            "|---|---|",
        ]

        for r in sorted(group_rows, key=lambda r: r["id"], reverse=True):
            description = str(r["description"] or "").replace("|", "\\|")
            tags_html = tag_pills_html(r["tags"])

            if description and tags_html:
                description_cell = f"{description}<br>{tags_html}"
            elif tags_html:
                description_cell = tags_html
            else:
                description_cell = description

            lines.append(
                f"| [{r['id']}]({r['id']}.md) | {description_cell} |"
            )

        group_dir = (
            docs_dir
            / "experiments"
            / group_rows[0]["date_label"]
            / fridge
        )

        group_dir.mkdir(parents=True, exist_ok=True)

        (group_dir / "index.md").write_text(
            "\n".join(lines) + "\n"
        )

def build_one_day_index(
    rows: list[dict],
    docs_dir: Path,
    date: str,
    fridge: str,
    date_label: str,
) -> None:
    """
    Rebuild only one date/fridge listing.
    """
    group_rows = [
        r
        for r in rows
        if r["date"] == date and r["fridge"] == fridge
    ]

    group_dir = (
        docs_dir
        / "experiments"
        / date_label
        / fridge
    )

    # If no experiments remain in this group, remove its generated index.
    if not group_rows:
        index_path = group_dir / "index.md"

        if index_path.exists():
            index_path.unlink()

        return

    lines = [
        f"# {date} / {fridge}\n",
        f"_{len(group_rows)} "
        f"experiment{'s' if len(group_rows) != 1 else ''}._\n",
        "| Experiment | Description |",
        "|---|---|",
    ]

    for r in sorted(
        group_rows,
        key=lambda r: r["id"],
        reverse=True,
    ):
        description = (
            str(r["description"] or "")
            .replace("|", "\\|")
        )

        tags_html = tag_pills_html(r["tags"])

        if description and tags_html:
            description_cell = f"{description}<br>{tags_html}"
        elif tags_html:
            description_cell = tags_html
        else:
            description_cell = description

        lines.append(
            f"| [{r['id']}]({r['id']}.md) | {description_cell} |"
        )

    group_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (group_dir / "index.md").write_text(
        "\n".join(lines) + "\n"
    )

def build_tags_page(docs_dir: Path) -> None:
    content = """# Tags

Browse FrostBook experiments by tag.

<!-- material/tags { toc: false } -->
"""
    (docs_dir / "tags.md").write_text(content)

def build_help_page(docs_dir: Path) -> None:
    """
    Copy the FrostBook Help page into generated docs/.
    """
    help_source = (
        RESOURCE_DIR
        / "help.md"
    )

    if not help_source.exists():
        print(
            "Warning: help.md not found; "
            "Help page was not generated."
        )
        return

    shutil.copyfile(
        help_source,
        docs_dir / "help.md",
    )

def copy_ui_resources(
    docs_dir: Path,
) -> None:
    """
    Copy FrostBook browser CSS and JavaScript into docs/.
    """

    for filename in (
        "extra.css",
        "extra.js",
    ):
        source = (
            RESOURCE_DIR
            / filename
        )

        if source.exists():
            shutil.copyfile(
                source,
                docs_dir / filename,
            )

def related_tag_set(row: dict) -> set[str]:
    """
    Return the tags that should count when calculating
    related experiments.
    """
    tags = set()

    for tag in row.get("tags", []):
        if any(
            tag.startswith(prefix)
            for prefix in RELATED_IGNORE_PREFIXES
        ):
            continue

        tags.add(tag)

    return tags


def compute_related_map(
    manifest: dict,
) -> dict:
    """
    Calculate up to RELATED_LIMIT related experiments
    for every experiment in the manifest.

    Ranking:
      1. Most shared tags
      2. Newest date
      3. Stable experiment key tie-breaker
    """
    experiments = manifest["experiments"]

    tag_sets = {
        key: related_tag_set(row)
        for key, row in experiments.items()
    }

    related_map = {}

    for key, row in experiments.items():
        this_tags = tag_sets[key]

        candidates = []

        for other_key, other_row in experiments.items():
            if other_key == key:
                continue

            shared_count = len(
                this_tags
                & tag_sets[other_key]
            )

            if shared_count < RELATED_MIN_SHARED_TAGS:
                continue

            candidates.append(
                (
                    shared_count,
                    str(other_row["date"]),
                    other_key,
                )
            )

        # Most shared tags first.
        #
        # If two experiments have the same number,
        # prefer the newer experiment.
        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            ),
            reverse=True,
        )

        selected = candidates[:RELATED_LIMIT]

        if selected:
            related_map[key] = [
                {
                    "key": other_key,
                    "shared": shared_count,
                }
                for (
                    shared_count,
                    _date,
                    other_key,
                ) in selected
            ]

    return related_map


def build_related_block(
    row: dict,
    related_items: list[dict],
    rows_by_key: dict,
    docs_dir: Path,
) -> str:
    """
    Build the Related Experiments markdown section for
    one experiment page.
    """
    if not related_items:
        return ""

    current_page = (
        docs_dir
        / "experiments"
        / row["date_label"]
        / row["fridge"]
        / f"{row['id']}.md"
    )

    lines = [
        RELATED_START,
        "---",
        "",
        "## Related Experiments",
        "",
    ]

    for item in related_items:
        other = rows_by_key.get(
            item["key"]
        )

        if other is None:
            continue

        target_page = (
            docs_dir
            / "experiments"
            / other["date_label"]
            / other["fridge"]
            / f"{other['id']}.md"
        )

        relative_link = Path(
            os.path.relpath(
                target_page,
                start=current_page.parent,
            )
        ).as_posix()

        shared = item["shared"]

        shared_label = (
            "shared tag"
            if shared == 1
            else "shared tags"
        )

        lines.append(
            f"- "
            f"[{other['id']} — "
            f"{other['date']} · "
            f"{other['fridge']}]"
            f"({relative_link})"
            f" — {shared} {shared_label}"
        )

    lines.append(
        RELATED_END
    )

    return "\n".join(lines)


def replace_related_block(
    page_path: Path,
    new_block: str,
) -> None:
    """
    Add, replace, or remove the generated Related Experiments
    section without touching the rest of the experiment page.
    """
    if not page_path.exists():
        return

    text = page_path.read_text()

    start_index = text.find(
        RELATED_START
    )

    end_index = text.find(
        RELATED_END
    )


    # -----------------------------------------------------
    # Existing related block
    # -----------------------------------------------------

    if (
        start_index != -1
        and end_index != -1
        and end_index >= start_index
    ):
        end_index += len(
            RELATED_END
        )

        before = text[:start_index].rstrip()
        after = text[end_index:].strip()

        pieces = []

        if before:
            pieces.append(before)

        if new_block:
            pieces.append(
                new_block.strip()
            )

        if after:
            pieces.append(after)

        new_text = (
            "\n\n".join(pieces)
            + "\n"
        )


    # -----------------------------------------------------
    # Page does not have a related block yet
    # -----------------------------------------------------

    else:
        new_text = text.rstrip()

        if new_block:
            new_text += (
                "\n\n"
                + new_block.strip()
            )

        new_text += "\n"


    # Only touch the file if something actually changed.
    if new_text != text:
        page_path.write_text(
            new_text
        )


def refresh_related_sections(
    manifest: dict,
    docs_dir: Path,
) -> None:
    """
    Recalculate related experiments using ONLY the manifest.

    Only experiment pages whose related list changed are
    rewritten.
    """
    rows_by_key = manifest["experiments"]

    old_map = manifest.setdefault(
        "related",
        {},
    )

    new_map = compute_related_map(
        manifest
    )

    # A relation can disappear as well as appear,
    # so compare keys from BOTH maps.
    candidate_keys = (
        set(old_map)
        | set(new_map)
    )

    changed_keys = {
        key
        for key in candidate_keys
        if (
            key in rows_by_key
            and old_map.get(key)
            != new_map.get(key)
        )
    }

    for key in changed_keys:
        row = rows_by_key[key]

        page_path = (
            docs_dir
            / "experiments"
            / row["date_label"]
            / row["fridge"]
            / f"{row['id']}.md"
        )

        block = build_related_block(
            row,
            new_map.get(key, []),
            rows_by_key,
            docs_dir,
        )

        replace_related_block(
            page_path,
            block,
        )

    manifest["related"] = new_map

    if changed_keys:
        print(
            f"Updated related links on "
            f"{len(changed_keys)} experiment page(s)."
        )

def read_skip_file(folder: Path) -> set[str]:
    """
    Read skip.txt from a folder.

    Entries can be separated by spaces, commas, or new lines.

    Anything after # is treated as a comment.
    """
    skip_path = folder / SKIP_FILENAME

    if not skip_path.exists():
        return set()

    skipped = set()

    for raw_line in skip_path.read_text().splitlines():
        line = raw_line.split("#", 1)[0].strip()

        if not line:
            continue

        entries = line.replace(",", " ").split()

        for entry in entries:
            entry = entry.strip()

            if entry:
                skipped.add(entry)

    return skipped


def discover_all_dates(data_dir: Path) -> set[str]:
    """
    Return all date directories, including skipped dates.

    This makes emoji assignments stable when skip.txt changes.
    """
    return {
        p.name
        for p in data_dir.iterdir()
        if p.is_dir()
    }

def is_experiment_skipped(
    data_dir: Path,
    date: str,
    fridge: str,
    exp_id: str,
) -> bool:
    """
    Check all three skip.txt levels for one experiment.
    Print exactly which rule caused a skip.
    """

    skipped_dates = read_skip_file(data_dir)

    if date in skipped_dates:
        print(
            f"Skip reason: date '{date}' found in "
            f"{data_dir / SKIP_FILENAME}"
        )
        return True

    date_dir = data_dir / date
    skipped_fridges = read_skip_file(date_dir)

    if fridge in skipped_fridges:
        print(
            f"Skip reason: fridge '{fridge}' found in "
            f"{date_dir / SKIP_FILENAME}"
        )
        return True

    fridge_dir = date_dir / fridge
    skipped_experiments = read_skip_file(fridge_dir)

    if exp_id in skipped_experiments:
        print(
            f"Skip reason: experiment '{exp_id}' found in "
            f"{fridge_dir / SKIP_FILENAME}"
        )
        return True

    return False

def discover_experiments(data_dir: Path):
    """
    Discover experiments while honoring hierarchical skip.txt files.

    data/skip.txt
        → skip dates

    data/<date>/skip.txt
        → skip fridges on that date

    data/<date>/<fridge>/skip.txt
        → skip experiment IDs
    """
    skipped_dates = read_skip_file(data_dir)

    for date_dir in sorted(data_dir.iterdir()):
        if not date_dir.is_dir():
            continue

        if date_dir.name in skipped_dates:
            print(f"Skipping date: {date_dir.name}")
            continue

        skipped_fridges = read_skip_file(date_dir)

        for fridge_dir in sorted(date_dir.iterdir()):
            if not fridge_dir.is_dir():
                continue

            if fridge_dir.name in skipped_fridges:
                print(
                    f"Skipping fridge: "
                    f"{date_dir.name}/{fridge_dir.name}"
                )
                continue

            skipped_experiments = read_skip_file(fridge_dir)

            for exp_dir in sorted(fridge_dir.iterdir()):
                if not exp_dir.is_dir():
                    continue

                if exp_dir.name in skipped_experiments:
                    print(
                        f"Skipping experiment: "
                        f"{date_dir.name}/"
                        f"{fridge_dir.name}/"
                        f"{exp_dir.name}"
                    )
                    continue

                yield (
                    date_dir.name,
                    fridge_dir.name,
                    exp_dir.name,
                    exp_dir,
                )

def experiment_from_path(
    path: Path,
    data_dir: Path,
) -> tuple[str, str, str, Path]:
    """
    Convert either an experiment directory or a file inside an
    experiment into:

        date, fridge, experiment ID, experiment directory

    Examples accepted:

        data/2026-08-10/zpc/0042
        data/2026-08-10/zpc/0042/notes.md
        data/2026-08-10/zpc/0042/metadata.yaml
    """
    path = path.resolve()
    data_dir = data_dir.resolve()

    if path.is_file():
        path = path.parent

    try:
        relative = path.relative_to(data_dir)
    except ValueError:
        raise ValueError(
            f"Update path must be inside the data directory: {data_dir}"
        )

    parts = relative.parts

    if len(parts) < 3:
        raise ValueError(
            "Update path must identify an experiment: "
            "data/<date>/<fridge>/<experiment>/..."
        )

    date, fridge, exp_id = parts[:3]

    exp_dir = (
        data_dir
        / date
        / fridge
        / exp_id
    )

    return date, fridge, exp_id, exp_dir

def update_one_experiment(
    update_path: Path,
    data_dir: Path,
    docs_dir: Path,
    manifest: dict,
) -> tuple[str, str, str]:
    """
    Incrementally rebuild, add, remove, or skip one experiment.

    Returns:
        date, fridge, date_label
    """
    date, fridge, exp_id, exp_dir = experiment_from_path(
        update_path,
        data_dir,
    )

    key = experiment_key(
        date,
        fridge,
        exp_id,
    )

    # -----------------------------------------------------
    # Experiment is skipped
    # -----------------------------------------------------

    if is_experiment_skipped(
        data_dir,
        date,
        fridge,
        exp_id,
    ):
        old_row = manifest["experiments"].pop(
            key,
            None,
        )

        if old_row:
            remove_rendered_experiment(
                date,
                fridge,
                exp_id,
                old_row["date_label"],
                docs_dir,
            )

            date_label = old_row["date_label"]
        else:
            emoji = get_or_assign_date_emoji(
                date,
                manifest,
            )

            date_label = f"{date}-{emoji}"

        print(f"Skipping experiment: {key}")

        return date, fridge, date_label


    # -----------------------------------------------------
    # Experiment folder does not exist
    # -----------------------------------------------------

    if not exp_dir.exists():
        old_row = manifest["experiments"].get(
            key
        )

        # FrostBook has never seen this experiment before,
        # so there is nothing we can update or remove.
        if old_row is None:
            raise SystemExit(
                f"ERROR: experiment not found: {exp_dir}\n"
                f"Nothing was updated."
            )

        # FrostBook knew about this experiment previously,
        # so the missing source folder means it was deleted.
        old_row = manifest["experiments"].pop(
            key
        )

        remove_rendered_experiment(
            date,
            fridge,
            exp_id,
            old_row["date_label"],
            docs_dir,
        )

        date_label = old_row["date_label"]

        print(
            f"Removed deleted experiment: {key}"
        )

        return date, fridge, date_label


    # -----------------------------------------------------
    # New or modified experiment
    # -----------------------------------------------------

    # This experiment page is about to be regenerated,
    # which removes its old Related Experiments block.
    #
    # Forget its cached related result so
    # refresh_related_sections() will restore it.
    manifest.setdefault(
        "related",
        {},
    ).pop(
        key,
        None,
    )
    
    date_emoji = get_or_assign_date_emoji(
        date,
        manifest,
    )

    date_label = f"{date}-{date_emoji}"

    remove_rendered_experiment(
        date,
        fridge,
        exp_id,
        date_label,
        docs_dir,
    )

    row = build_experiment_page(
        date,
        fridge,
        exp_id,
        exp_dir,
        docs_dir,
        date_emoji,
    )

    manifest["experiments"][key] = row

    print(f"Updated experiment: {key}")

    return date, fridge, date_label

def sync_one_fridge(
    date: str,
    fridge: str,
    data_dir: Path,
    docs_dir: Path,
    manifest: dict,
) -> set[tuple[str, str, str]]:
    """
    Synchronize exactly one fridge.

    Only data/<date>/<fridge>/ is scanned.

    This:
      - adds new experiments
      - updates existing experiments
      - removes deleted experiments
      - removes newly skipped experiments
    """

    date_dir = data_dir / date
    fridge_dir = date_dir / fridge

    date_emoji = get_or_assign_date_emoji(
        date,
        manifest,
    )

    date_label = f"{date}-{date_emoji}"

    affected = {
        (date, fridge, date_label)
    }

    prefix = f"{date}/{fridge}/"

    # Experiments FrostBook already knows about
    # from this particular date/fridge.
    old_keys = [
        key
        for key in list(manifest["experiments"])
        if key.startswith(prefix)
    ]


    # =====================================================
    # WHOLE DATE IS SKIPPED
    # =====================================================

    if date in read_skip_file(data_dir):
        for key in old_keys:
            old_row = manifest["experiments"].pop(key)

            remove_rendered_experiment(
                old_row["date"],
                old_row["fridge"],
                old_row["id"],
                old_row["date_label"],
                docs_dir,
            )

        print(
            f"Skipping fridge because date is skipped: "
            f"{date}/{fridge}"
        )

        return affected


    # =====================================================
    # WHOLE FRIDGE IS SKIPPED
    # =====================================================

    if fridge in read_skip_file(date_dir):
        for key in old_keys:
            old_row = manifest["experiments"].pop(key)

            remove_rendered_experiment(
                old_row["date"],
                old_row["fridge"],
                old_row["id"],
                old_row["date_label"],
                docs_dir,
            )

        print(
            f"Skipping fridge: {date}/{fridge}"
        )

        return affected


    # =====================================================
    # FRIDGE FOLDER DOES NOT EXIST
    # =====================================================

    if not fridge_dir.exists():

        # FrostBook knew this fridge before.
        # Treat the missing folder as a deletion.
        if old_keys:
            for key in old_keys:
                old_row = manifest["experiments"].pop(key)

                remove_rendered_experiment(
                    old_row["date"],
                    old_row["fridge"],
                    old_row["id"],
                    old_row["date_label"],
                    docs_dir,
                )

            print(
                f"Removed deleted fridge: "
                f"{date}/{fridge}"
            )

            return affected

        # It doesn't exist AND FrostBook has never seen it.
        # Most likely the user entered a bad path.
        raise SystemExit(
            f"ERROR: fridge not found: {fridge_dir}\n"
            f"Nothing was updated."
        )


    # =====================================================
    # CURRENT EXPERIMENTS IN THIS FRIDGE
    # =====================================================

    skipped_experiments = read_skip_file(
        fridge_dir
    )

    current_ids = {
        p.name
        for p in fridge_dir.iterdir()
        if p.is_dir()
        and p.name not in skipped_experiments
    }


    # =====================================================
    # REMOVE DELETED OR NEWLY SKIPPED EXPERIMENTS
    # =====================================================

    for key in old_keys:
        old_row = manifest["experiments"].get(key)

        if (
            old_row
            and old_row["id"] not in current_ids
        ):
            remove_rendered_experiment(
                old_row["date"],
                old_row["fridge"],
                old_row["id"],
                old_row["date_label"],
                docs_dir,
            )

            del manifest["experiments"][key]

            print(
                f"Removed experiment: {key}"
            )


    # =====================================================
    # ADD / UPDATE CURRENT EXPERIMENTS
    # =====================================================

    for exp_id in sorted(current_ids):
        exp_dir = fridge_dir / exp_id

        update_one_experiment(
            exp_dir,
            data_dir,
            docs_dir,
            manifest,
        )


    print(
        f"Synced fridge: "
        f"{date}/{fridge} "
        f"({len(current_ids)} experiment(s))"
    )

    return affected

def sync_one_date(
    date: str,
    data_dir: Path,
    docs_dir: Path,
    manifest: dict,
) -> set[tuple[str, str, str]]:
    """
    Synchronize exactly one date.

    Only data/<date>/ is scanned.
    No other dates are read.
    """

    date_dir = data_dir / date


    # =====================================================
    # FIND WHAT FROSTBOOK ALREADY KNOWS ABOUT THIS DATE
    # =====================================================

    old_rows = [
        row
        for row in manifest["experiments"].values()
        if row["date"] == date
    ]

    old_fridges = {
        row["fridge"]
        for row in old_rows
    }


    # =====================================================
    # DETERMINE DATE LABEL / EMOJI
    # =====================================================

    if old_rows:
        date_label = old_rows[0]["date_label"]

    else:
        emoji = get_or_assign_date_emoji(
            date,
            manifest,
        )

        date_label = f"{date}-{emoji}"


    # =====================================================
    # WHOLE DATE IS SKIPPED
    # =====================================================

    if date in read_skip_file(data_dir):

        affected = {
            (
                date,
                fridge,
                date_label,
            )
            for fridge in old_fridges
        }

        for key in list(
            manifest["experiments"]
        ):
            row = manifest["experiments"][key]

            if row["date"] != date:
                continue

            remove_rendered_experiment(
                row["date"],
                row["fridge"],
                row["id"],
                row["date_label"],
                docs_dir,
            )

            del manifest["experiments"][key]

        print(
            f"Skipping date: {date}"
        )

        return affected


    # =====================================================
    # DATE DIRECTORY DOES NOT EXIST
    # =====================================================

    if not date_dir.exists():

        # FrostBook knew the date before.
        # Therefore the date was deleted.
        if old_rows:

            affected = {
                (
                    date,
                    fridge,
                    date_label,
                )
                for fridge in old_fridges
            }

            for key in list(
                manifest["experiments"]
            ):
                row = manifest["experiments"][key]

                if row["date"] != date:
                    continue

                remove_rendered_experiment(
                    row["date"],
                    row["fridge"],
                    row["id"],
                    row["date_label"],
                    docs_dir,
                )

                del manifest["experiments"][key]

            print(
                f"Removed deleted date: {date}"
            )

            return affected

        # Date doesn't exist and FrostBook never knew it.
        raise SystemExit(
            f"ERROR: date not found: {date_dir}\n"
            f"Nothing was updated."
        )


    # =====================================================
    # CURRENT FRIDGES IN THIS DATE
    # =====================================================

    current_fridges = {
        p.name
        for p in date_dir.iterdir()
        if p.is_dir()
    }


    # Include old fridges as well.
    #
    # That way if a fridge used to exist but has now
    # disappeared, sync_one_fridge() can remove it.
    all_fridges = (
        current_fridges
        | old_fridges
    )


    # =====================================================
    # SYNC EACH FRIDGE IN THIS DATE ONLY
    # =====================================================

    affected = set()

    for fridge in sorted(all_fridges):

        affected.update(
            sync_one_fridge(
                date,
                fridge,
                data_dir,
                docs_dir,
                manifest,
            )
        )


    print(
        f"Synced date: {date}"
    )

    return affected

def update_scope(
    update_path: Path,
    data_dir: Path,
    docs_dir: Path,
    manifest: dict,
) -> set[tuple[str, str, str]]:
    """
    Decide the update scope from the supplied path.

    Supported:

        data/<date>
            -> update the whole date

        data/<date>/<fridge>
            -> update the whole fridge

        data/<date>/<fridge>/<experiment>
            -> update one experiment

        data/<date>/<fridge>/<experiment>/<file>
            -> update the experiment containing that file
    """

    update_path = update_path.resolve()
    data_dir = data_dir.resolve()

    try:
        relative = update_path.relative_to(
            data_dir
        )

    except ValueError:
        raise SystemExit(
            f"ERROR: update path must be inside "
            f"the data directory:\n{data_dir}"
        )


    parts = relative.parts


    # =====================================================
    # ONE WHOLE DATE
    # =====================================================
    #
    # Example:
    #
    # data/2026-08-05
    #

    if len(parts) == 1:

        date = parts[0]

        return sync_one_date(
            date,
            data_dir,
            docs_dir,
            manifest,
        )


    # =====================================================
    # ONE WHOLE FRIDGE
    # =====================================================
    #
    # Example:
    #
    # data/2026-08-05/zpc
    #

    if len(parts) == 2:

        date, fridge = parts

        return sync_one_fridge(
            date,
            fridge,
            data_dir,
            docs_dir,
            manifest,
        )


    # =====================================================
    # ONE EXPERIMENT OR FILE INSIDE EXPERIMENT
    # =====================================================
    #
    # Examples:
    #
    # data/2026-08-05/zpc/0001
    #
    # data/2026-08-05/zpc/0001/notes.md
    #

    if len(parts) >= 3:

        date, fridge, date_label = (
            update_one_experiment(
                update_path,
                data_dir,
                docs_dir,
                manifest,
            )
        )

        return {
            (
                date,
                fridge,
                date_label,
            )
        }


    raise SystemExit(
        "ERROR: --update must point to a "
        "date, fridge, experiment, or file "
        "inside an experiment."
    )

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data-dir",
        default="data",
    )

    parser.add_argument(
        "--docs-dir",
        default="docs",
    )

    parser.add_argument(
        "--update",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Incrementally synchronize a date, fridge, experiment, "
            "or file inside an experiment without rescanning the "
            "full data tree. May be supplied multiple times."
        ),
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    docs_dir = Path(args.docs_dir)

    manifest_path = (
        Path(__file__).parent
        / MANIFEST_FILENAME
    )

    if not data_dir.exists():
        raise SystemExit(f"Data directory not found: {data_dir}")

    # =========================================================
    # INCREMENTAL UPDATE MODE
    # =========================================================

    if args.update:
        if not docs_dir.exists():
            raise SystemExit(
                "No existing FrostBook build found. "
                "Run a normal full build first."
            )

        if not manifest_path.exists():
            raise SystemExit(
                "No FrostBook manifest found. "
                "Run a normal full build first."
            )

        manifest = load_manifest(
            manifest_path
        )

        affected_groups = set()

        for update in args.update:

            affected_groups.update(
                update_scope(
                    Path(update),
                    data_dir,
                    docs_dir,
                    manifest,
                )
            )

        rows = manifest_rows(
            manifest
        )

        copy_ui_resources(
            docs_dir
        )

        # Rebuild homepage from lightweight manifest only.
        build_index(
            rows,
            docs_dir,
        )

        # Only rebuild the day/fridge tables affected.
        for date, fridge, date_label in affected_groups:
            build_one_day_index(
                rows,
                docs_dir,
                date,
                fridge,
                date_label,
            )

        build_tags_page(
            docs_dir
        )

        build_help_page(
            docs_dir
        )

        refresh_related_sections(
            manifest,
            docs_dir,
        )

        save_manifest(
            manifest_path,
            manifest,
        )

        print(
            f"Incremental update complete for "
            f"{len(args.update)} target(s)."
        )

        return

    shutil.rmtree(docs_dir, ignore_errors=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    copy_ui_resources(
        docs_dir
    )

    date_emojis = assign_date_emojis(
        discover_all_dates(data_dir)
    )

    experiments = list(
        discover_experiments(data_dir)
    )

    rows = []
    for date, fridge, exp_id, exp_dir in experiments:
        row = build_experiment_page(date, fridge, exp_id, exp_dir, docs_dir, date_emojis[date])
        rows.append(row)

    build_index(rows, docs_dir)
    build_day_indexes(rows, docs_dir)
    build_tags_page(docs_dir)
    build_help_page(docs_dir)

    manifest = {
        "version": 1,
        "date_emojis": date_emojis,
        "experiments": {
            experiment_key(
                row["date"],
                row["fridge"],
                row["id"],
            ): row
            for row in rows
        },
        "related": {},
    }

    refresh_related_sections(
        manifest,
        docs_dir,
    )

    save_manifest(
        manifest_path,
        manifest,
    )

    print(
        f"Generated {len(rows)} experiment pages "
        f"into {docs_dir}/experiments/"
    )

if __name__ == "__main__":
    main()
