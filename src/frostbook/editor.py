#!/usr/bin/env python3

"""
FrostBook local browser editor.

This is intentionally separate from the read-only generator.

It allows the browser to:
- read notes.md
- save notes.md
- upload PNG/JPG/JPEG plots and images
- respect per-experiment .frostbook-lock files
- trigger FrostBook's existing incremental renderer
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import uvicorn
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# =========================================================
# PATHS
# =========================================================

DATA_DIR = Path("data").resolve()
DOCS_DIR = Path("docs").resolve()


def configure_paths(
    data_dir: Path,
    docs_dir: Path,
) -> None:
    global DATA_DIR
    global DOCS_DIR

    DATA_DIR = data_dir.resolve()
    DOCS_DIR = docs_dir.resolve()


# =========================================================
# EDITOR SETTINGS
# =========================================================

LOCK_FILENAME = ".frostbook-lock"

ALLOWED_UPLOAD_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".pdf",
}

DELETABLE_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".pdf",
}

MAX_UPLOAD_BYTES = (
    25 * 1024 * 1024
)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="FrostBook Editor",
)


# MkDocs normally runs on port 8000.
#
# The editor runs on port 8765.
# Different ports are different browser origins,
# so explicitly allow the local MkDocs origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "PUT",
        "POST",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=["*"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class NotesPayload(BaseModel):
    notes: str


# =========================================================
# EXPERIMENT PATH VALIDATION
# =========================================================

def experiment_dir(
    date: str,
    fridge: str,
    exp_id: str,
) -> Path:
    """
    Safely resolve:

        data/<date>/<fridge>/<exp_id>

    The resolved directory must stay inside DATA_DIR.
    """

    for label, value in (
        ("date", date),
        ("fridge", fridge),
        ("experiment", exp_id),
    ):
        if (
            not value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or Path(value).name != value
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid {label}: {value}"
                ),
            )

    path = (
        DATA_DIR
        / date
        / fridge
        / exp_id
    ).resolve()

    try:
        path.relative_to(
            DATA_DIR
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid experiment path."
            ),
        )

    if not path.is_dir():
        raise HTTPException(
            status_code=404,
            detail=(
                "Experiment not found: "
                f"{date}/{fridge}/{exp_id}"
            ),
        )

    return path


# =========================================================
# EDIT LOCKS
# =========================================================

def read_experiment_lock(
    exp_dir: Path,
) -> set[str]:
    """
    Read optional .frostbook-lock.

    Supported entries:

        notes
        images
        all

    Entries may use spaces, commas, or new lines.
    Anything after # is a comment.
    """

    lock_path = (
        exp_dir
        / LOCK_FILENAME
    )

    if not lock_path.exists():
        return set()

    locks = set()

    for raw_line in (
        lock_path
        .read_text()
        .splitlines()
    ):
        line = (
            raw_line
            .split("#", 1)[0]
            .strip()
            .lower()
        )

        if not line:
            continue

        entries = (
            line
            .replace(",", " ")
            .split()
        )

        for entry in entries:
            if entry:
                locks.add(entry)

    return locks


def is_locked(
    exp_dir: Path,
    action: str,
) -> bool:
    locks = read_experiment_lock(
        exp_dir
    )

    return (
        "all" in locks
        or action in locks
    )


def require_unlocked(
    exp_dir: Path,
    action: str,
) -> None:
    if is_locked(
        exp_dir,
        action,
    ):
        raise HTTPException(
            status_code=423,
            detail=(
                f"This experiment is locked "
                f"for {action} editing."
            ),
        )


# =========================================================
# RERENDER ONE EXPERIMENT
# =========================================================

def rerender_experiment(
    exp_dir: Path,
) -> None:
    """
    Use FrostBook's existing incremental update system.

    This intentionally calls the public FrostBook CLI
    rather than duplicating generator logic here.
    """

    command = [
        sys.executable,
        "-m",
        "frostbook",
        "--data-dir",
        str(DATA_DIR),
        "--docs-dir",
        str(DOCS_DIR),
        "--update",
        str(exp_dir),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": (
                    "The source file was changed, "
                    "but FrostBook could not "
                    "rerender the experiment."
                ),
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )

    if result.stdout.strip():
        print(
            result.stdout.strip()
        )


# =========================================================
# IMAGE FILENAMES
# =========================================================

def unique_upload_path(
    exp_dir: Path,
    original_filename: str,
) -> Path:
    """
    Sanitize an image filename and avoid overwriting an
    existing image.

        plot.png
        plot_2.png
        plot_3.png
    """

    original_filename = Path(
        original_filename or "image"
    ).name

    suffix = Path(
        original_filename
    ).suffix.lower()

    if (
        suffix
        not in ALLOWED_UPLOAD_EXTENSIONS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported image type. "
                "Use PNG, JPG, JPEG, or PDF."
            ),
        )

    stem = Path(
        original_filename
    ).stem

    stem = re.sub(
        r"[^A-Za-z0-9._ -]+",
        "_",
        stem,
    )

    stem = stem.strip(
        " ."
    )

    if not stem:
        stem = "image"

    destination = (
        exp_dir
        / f"{stem}{suffix}"
    )

    counter = 2

    while destination.exists():
        destination = (
            exp_dir
            / f"{stem}_{counter}{suffix}"
        )

        counter += 1

    return destination


def validate_uploaded_image(
    path: Path,
) -> None:
    """
    Verify that an uploaded PNG, JPG, JPEG, or PDF
    matches its filename extension.
    """

    with path.open("rb") as f:
        header = f.read(1024)

    suffix = path.suffix.lower()

    if suffix == ".png":
        valid = header.startswith(
            b"\x89PNG\r\n\x1a\n"
        )

    elif suffix in {
        ".jpg",
        ".jpeg",
    }:
        valid = header.startswith(
            b"\xff\xd8\xff"
        )

    elif suffix == ".pdf":
        valid = (
            b"%PDF-" in header
        )

    else:
        valid = False

    if not valid:
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded file does not "
                "match its file extension."
            ),
        )


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "FrostBook Editor",
    }


# =========================================================
# EDITOR STATE / LOCK STATE
# =========================================================

@app.get(
    "/api/experiment/"
    "{date}/{fridge}/{exp_id}/state"
)
def editor_state(
    date: str,
    fridge: str,
    exp_id: str,
):
    exp_dir = experiment_dir(
        date,
        fridge,
        exp_id,
    )

    locks = read_experiment_lock(
        exp_dir
    )

    return {
        "ok": True,
        "locks": sorted(locks),
        "notes_locked": (
            "all" in locks
            or "notes" in locks
        ),
        "images_locked": (
            "all" in locks
            or "images" in locks
        ),
    }


# =========================================================
# READ NOTES
# =========================================================

@app.get(
    "/api/experiment/"
    "{date}/{fridge}/{exp_id}/notes"
)
def get_notes(
    date: str,
    fridge: str,
    exp_id: str,
):
    exp_dir = experiment_dir(
        date,
        fridge,
        exp_id,
    )

    notes_path = (
        exp_dir
        / "notes.md"
    )

    if notes_path.exists():
        notes = notes_path.read_text(
            encoding="utf-8"
        )

    else:
        notes = ""

    return {
        "ok": True,
        "notes": notes,
    }


# =========================================================
# SAVE NOTES
# =========================================================

@app.put(
    "/api/experiment/"
    "{date}/{fridge}/{exp_id}/notes"
)
def save_notes(
    date: str,
    fridge: str,
    exp_id: str,
    payload: NotesPayload,
):
    exp_dir = experiment_dir(
        date,
        fridge,
        exp_id,
    )

    require_unlocked(
        exp_dir,
        "notes",
    )

    notes_path = (
        exp_dir
        / "notes.md"
    )

    temp_path = (
        exp_dir
        / ".notes.md.frostbook.tmp"
    )

    temp_path.write_text(
        payload.notes,
        encoding="utf-8",
    )

    temp_path.replace(
        notes_path
    )

    rerender_experiment(
        exp_dir
    )

    return {
        "ok": True,
        "message": "Notes saved.",
    }


# =========================================================
# UPLOAD PLOT / IMAGE
# =========================================================

@app.post(
    "/api/experiment/"
    "{date}/{fridge}/{exp_id}/image"
)
async def upload_image(
    date: str,
    fridge: str,
    exp_id: str,
    file: UploadFile = File(...),
):
    exp_dir = experiment_dir(
        date,
        fridge,
        exp_id,
    )

    require_unlocked(
        exp_dir,
        "images",
    )

    destination = unique_upload_path(
        exp_dir,
        file.filename or "image",
    )

    total_bytes = 0

    try:
        with destination.open(
            "xb"
        ) as output:

            while True:
                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                total_bytes += len(chunk)

                if (
                    total_bytes
                    > MAX_UPLOAD_BYTES
                ):
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "File is too large. "
                            "Maximum size is 25 MB."
                        ),
                    )

                output.write(
                    chunk
                )

        validate_uploaded_image(
            destination
        )

    except Exception:
        if destination.exists():
            destination.unlink()

        raise

    finally:
        await file.close()

    rerender_experiment(
        exp_dir
    )

    return {
        "ok": True,
        "message": "Image uploaded.",
        "filename": destination.name,
    }

# =========================================================
# DELETE PLOT / IMAGE
# =========================================================

@app.delete(
    "/api/experiment/"
    "{date}/{fridge}/{exp_id}/image/{filename}"
)
def delete_image(
    date: str,
    fridge: str,
    exp_id: str,
    filename: str,
):
    exp_dir = experiment_dir(
        date,
        fridge,
        exp_id,
    )

    # The same "images" lock controls both
    # uploading and deleting images.
    require_unlocked(
        exp_dir,
        "images",
    )


    # -----------------------------------------------------
    # VALIDATE FILENAME
    # -----------------------------------------------------

    if (
        not filename
        or filename in {".", ".."}
        or Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid image filename.",
        )


    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    if (
        suffix
        not in DELETABLE_IMAGE_EXTENSIONS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "This file type cannot be "
                "deleted through FrostBook."
            ),
        )


    image_path = (
        exp_dir
        / filename
    ).resolve()


    # Make absolutely sure the requested file
    # is still inside this experiment directory.
    try:
        image_path.relative_to(
            exp_dir.resolve()
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid image path.",
        )


    if not image_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Image not found: {filename}"
            ),
        )


    # -----------------------------------------------------
    # DELETE SOURCE FILE
    # -----------------------------------------------------

    image_path.unlink()


    # Rebuild only this experiment so the deleted
    # plot disappears from FrostBook.
    rerender_experiment(
        exp_dir
    )


    return {
        "ok": True,
        "message": "Image deleted.",
        "filename": filename,
    }

# =========================================================
# COMMAND-LINE ENTRY POINT
# =========================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run FrostBook's local browser "
            "editing server."
        )
    )

    parser.add_argument(
        "--data-dir",
        default="data",
    )

    parser.add_argument(
        "--docs-dir",
        default="docs",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8765,
    )

    args = parser.parse_args()

    configure_paths(
        Path(args.data_dir),
        Path(args.docs_dir),
    )

    if not DATA_DIR.exists():
        raise SystemExit(
            f"Data directory not found: "
            f"{DATA_DIR}"
        )

    if not DOCS_DIR.exists():
        raise SystemExit(
            f"Docs directory not found: "
            f"{DOCS_DIR}\n"
            "Run one full FrostBook build first."
        )

    print(
        "FrostBook editor"
    )

    print(
        f"Data: {DATA_DIR}"
    )

    print(
        f"Docs: {DOCS_DIR}"
    )

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()