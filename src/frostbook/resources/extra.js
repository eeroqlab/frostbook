function openFrostBookTag() {
  /*
   * TABLE LINKS
   *
   * Example:
   * /tags/?tag=procedure%2Fstdoor_sweep
   */
  const params = new URLSearchParams(window.location.search);
  const requestedTag = params.get("tag");

  if (requestedTag) {
    const allTagGroups = document.querySelectorAll(
      "details.frost-tag-group[data-frost-tag]"
    );

    let target = null;

    for (const group of allTagGroups) {
      if (group.dataset.frostTag === requestedTag) {
        target = group;
        break;
      }
    }

    if (target) {
      openTagAndParents(target);
      return;
    }
  }


  /*
   * MATERIAL'S NATIVE TAG LINKS
   *
   * Keep support for tags clicked directly on experiment pages,
   * since Material already generates those links correctly.
   */
  if (window.location.hash) {
    const id = decodeURIComponent(
      window.location.hash.substring(1)
    );

    const anchor = document.getElementById(id);

    if (anchor) {
      const target = anchor.closest(
        "details.frost-tag-group"
      );

      if (target) {
        openTagAndParents(target);
      }
    }
  }
}


function openTagAndParents(target) {
  // Save the specific child dropdown we want to show.
  const leaf = target;

  // Open this dropdown and every parent dropdown.
  let current = target;

  while (current) {
    current.open = true;

    current = current.parentElement?.closest(
      "details.frost-tag-group"
    );
  }

  // Wait until the browser has expanded everything,
  // then smoothly move the chosen tag into view.
  requestAnimationFrame(() => {
    leaf.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
  });
}


/*
 * Material navigation.instant doesn't always reload the whole page,
 * so run after every Material page navigation.
 */
if (typeof document$ !== "undefined") {
  document$.subscribe(function () {
    openFrostBookTag();
  });
}


/*
 * Also cover a normal browser page load.
 */
window.addEventListener(
  "DOMContentLoaded",
  openFrostBookTag
);


/*
 * Keep native Material hash links working if the hash changes
 * while we're already on the Tags page.
 */
window.addEventListener(
  "hashchange",
  openFrostBookTag
);

/* =========================================================
   FROSTBOOK HELP BUTTON
   ========================================================= */

function initFrostHelpLink() {
  const header = document.querySelector(
    ".md-header__inner"
  );

  if (!header) {
    return;
  }

  // Prevent duplicates.
  if (
    header.querySelector(
      ".frost-help-link"
    )
  ) {
    return;
  }


  const homeLink = document.querySelector(
    "a.md-logo"
  );

  const homeUrl = homeLink
    ? homeLink.href
    : `${window.location.origin}/`;


  const helpLink =
    document.createElement("a");

  helpLink.className =
    "frost-help-link";

  helpLink.href = new URL(
    "help/",
    homeUrl
  ).href;

  helpLink.textContent =
    "Help";

  helpLink.setAttribute(
    "aria-label",
    "FrostBook Help"
  );


  // Put Help immediately before Material's search control.
  const searchButton =
    header.querySelector(
      'label[for="__search"]'
    );


  if (searchButton) {
    header.insertBefore(
      helpLink,
      searchButton
    );
  } else {
    header.appendChild(
      helpLink
    );
  }
}


/*
 * Material instant navigation may swap page content
 * without doing a normal browser reload.
 */
if (
  typeof document$ !== "undefined"
) {
  document$.subscribe(
    function () {
      initFrostHelpLink();
    }
  );
}


/*
 * Normal first page load.
 */
window.addEventListener(
  "DOMContentLoaded",
  initFrostHelpLink
);

/* =========================================================
   KEEP STAR FIRST ON TAGS PAGE
   ========================================================= */

function moveStarTagFirst() {
  const star = document.querySelector(
    'details.frost-tag-group[data-frost-tag="star"]'
  );

  if (!star) {
    return;
  }

  const parent = star.parentElement;

  if (!parent) {
    return;
  }

  const firstTagGroup = Array.from(
    parent.children
  ).find(
    element =>
      element.matches?.(
        "details.frost-tag-group"
      )
  );

  if (
    firstTagGroup
    && firstTagGroup !== star
  ) {
    parent.insertBefore(
      star,
      firstTagGroup
    );
  }
}


/* Material instant navigation */
if (
  typeof document$ !== "undefined"
) {
  document$.subscribe(
    function () {
      moveStarTagFirst();
    }
  );
}


/* Normal page load */
window.addEventListener(
  "DOMContentLoaded",
  moveStarTagFirst
);

/* =========================================================
   KEEP STAR CLOSED BY DEFAULT
   ========================================================= */

function closeStarByDefault() {
  const star = document.querySelector(
    'details.frost-tag-group[data-frost-tag="star"]'
  );

  if (!star) {
    return;
  }


  /*
   * If the user specifically navigated to the star tag,
   * allow the existing tag-opening code to open it.
   */
  const params =
    new URLSearchParams(
      window.location.search
    );

  const requestedTag =
    params.get("tag");

  if (requestedTag === "star") {
    return;
  }


  /*
   * Also preserve Material's native hash links.
   */
  if (window.location.hash) {
    const id = decodeURIComponent(
      window.location.hash.substring(1)
    );

    const anchor =
      document.getElementById(id);

    const requestedGroup =
      anchor?.closest(
        "details.frost-tag-group"
      );

    if (
      requestedGroup?.dataset.frostTag
      === "star"
    ) {
      return;
    }
  }


  /*
   * Normal visit to /tags/:
   * keep star collapsed.
   */
  star.open = false;
}


/* Material instant navigation */
if (
  typeof document$ !== "undefined"
) {
  document$.subscribe(
    function () {
      closeStarByDefault();
    }
  );
}


/* Normal page load */
window.addEventListener(
  "DOMContentLoaded",
  closeStarByDefault
);

/* =========================================================
   CLICK FROSTBOOK HEADER TITLE → HOME
   ========================================================= */

function initFrostBookHomeTitle() {
  const title = document.querySelector(
    ".md-header__title"
  );

  if (!title) {
    return;
  }

  // Don't attach the click behavior twice.
  if (title.dataset.frostHomeReady) {
    return;
  }

  title.dataset.frostHomeReady = "true";

  // Material's logo already points to the correct homepage,
  // so reuse its URL.
  const logoLink = document.querySelector(
    "a.md-logo"
  );

  const homeUrl = logoLink
    ? logoLink.href
    : `${window.location.origin}/`;

  title.setAttribute(
    "role",
    "link"
  );

  title.setAttribute(
    "tabindex",
    "0"
  );

  title.setAttribute(
    "aria-label",
    "Go to FrostBook home"
  );

  title.addEventListener(
    "click",
    () => {
      window.location.href = homeUrl;
    }
  );

  title.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Enter"
        || event.key === " "
      ) {
        event.preventDefault();
        window.location.href = homeUrl;
      }
    }
  );
}


/* Material instant navigation */
if (
  typeof document$ !== "undefined"
) {
  document$.subscribe(
    function () {
      initFrostBookHomeTitle();
    }
  );
}


/* Normal page load */
window.addEventListener(
  "DOMContentLoaded",
  initFrostBookHomeTitle
);

/* =========================================================
   FROSTBOOK BROWSER EDITOR
   ========================================================= */

const FROST_EDITOR_API =
  "http://127.0.0.1:8765";


function frostEditorInfo(element) {
  return {
    date: element.dataset.date,
    fridge: element.dataset.fridge,
    experiment:
      element.dataset.experiment
  };
}


function frostEditorUrl(
  info,
  endpoint
) {
  const date =
    encodeURIComponent(
      info.date
    );

  const fridge =
    encodeURIComponent(
      info.fridge
    );

  const experiment =
    encodeURIComponent(
      info.experiment
    );

  return (
    `${FROST_EDITOR_API}` +
    `/api/experiment/` +
    `${date}/${fridge}/${experiment}/` +
    endpoint
  );
}


function setFrostEditorStatus(
  element,
  message,
  isError = false
) {
  element.textContent =
    message;

  element.classList.toggle(
    "frost-editor-status--error",
    isError
  );
}


async function frostEditorFetch(
  url,
  options = {}
) {
  let response;

  try {
    response = await fetch(
      url,
      options
    );

  } catch (error) {
    throw new Error(
      "FrostBook editor is not running. " +
      "Start it with: frostbook-editor"
    );
  }


  let data = null;

  try {
    data =
      await response.json();

  } catch (_) {
    // Response did not contain JSON.
  }


  if (!response.ok) {
    let message =
      `Editor request failed ` +
      `(${response.status}).`;

    if (data?.detail) {
      if (
        typeof data.detail
        === "string"
      ) {
        message =
          data.detail;

      } else if (
        data.detail.message
      ) {
        message =
          data.detail.message;
      }
    }

    throw new Error(
      message
    );
  }

  return data;
}


/* =========================================================
   LOCK STATE
   ========================================================= */

async function frostEditorState(
  info
) {
  return frostEditorFetch(
    frostEditorUrl(
      info,
      "state"
    )
  );
}


/* =========================================================
   NOTES EDITOR
   ========================================================= */

function initFrostNotesEditor(
  container
) {
  if (
    container.dataset
      .frostEditorReady
  ) {
    return;
  }

  container.dataset
    .frostEditorReady =
    "true";


  const info =
    frostEditorInfo(
      container
    );


  const row =
    document.createElement(
      "div"
    );

  row.className =
    "frost-editor-row";


  const editButton =
    document.createElement(
      "button"
    );

  editButton.type =
    "button";

  editButton.className =
    "frost-editor-button";

  editButton.textContent =
    "Edit Notes";


  const status =
    document.createElement(
      "span"
    );

  status.className =
    "frost-editor-status";


  row.append(
    editButton,
    status
  );


  const editor =
    document.createElement(
      "div"
    );

  editor.className =
    "frost-notes-editor";

  editor.hidden = true;


  const textarea =
    document.createElement(
      "textarea"
    );

  textarea.className =
    "frost-notes-textarea";

  textarea.spellcheck =
    true;


  const actionRow =
    document.createElement(
      "div"
    );

  actionRow.className =
    "frost-editor-row";


  const saveButton =
    document.createElement(
      "button"
    );

  saveButton.type =
    "button";

  saveButton.className =
    "frost-editor-button " +
    "frost-editor-button--primary";

  saveButton.textContent =
    "Save Notes";


  const cancelButton =
    document.createElement(
      "button"
    );

  cancelButton.type =
    "button";

  cancelButton.className =
    "frost-editor-button";

  cancelButton.textContent =
    "Cancel";


  actionRow.append(
    saveButton,
    cancelButton
  );

  editor.append(
    textarea,
    actionRow
  );

  container.append(
    row,
    editor
  );


  /*
   * Check whether notes are locked.
   *
   * If the editor server is not running,
   * don't show an error yet. The user will
   * receive a useful error if they click.
   */
  frostEditorState(
    info
  )
    .then(
      data => {
        if (
          data.notes_locked
        ) {
          editButton.disabled =
            true;

          editButton.textContent =
            "🔒 Notes locked";
        }
      }
    )
    .catch(
      () => {}
    );


  /* ---------------------------------------------
     OPEN
     --------------------------------------------- */

  editButton.addEventListener(
    "click",
    async () => {
      editButton.disabled =
        true;

      setFrostEditorStatus(
        status,
        "Loading..."
      );

      try {
        const data =
          await frostEditorFetch(
            frostEditorUrl(
              info,
              "notes"
            )
          );

        textarea.value =
          data.notes ?? "";

        editor.hidden =
          false;

        editButton.hidden =
          true;

        setFrostEditorStatus(
          status,
          ""
        );

        textarea.focus();

      } catch (error) {
        setFrostEditorStatus(
          status,
          error.message,
          true
        );

      } finally {
        editButton.disabled =
          false;
      }
    }
  );


  /* ---------------------------------------------
     CANCEL
     --------------------------------------------- */

  cancelButton.addEventListener(
    "click",
    () => {
      editor.hidden =
        true;

      editButton.hidden =
        false;

      setFrostEditorStatus(
        status,
        ""
      );
    }
  );


  /* ---------------------------------------------
     SAVE
     --------------------------------------------- */

  saveButton.addEventListener(
    "click",
    async () => {
      saveButton.disabled =
        true;

      cancelButton.disabled =
        true;

      setFrostEditorStatus(
        status,
        "Saving..."
      );

      try {
        await frostEditorFetch(
          frostEditorUrl(
            info,
            "notes"
          ),
          {
            method: "PUT",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
              notes:
                textarea.value
            })
          }
        );

        setFrostEditorStatus(
          status,
          "Saved. Refreshing..."
        );

        setTimeout(
          () => {
            window.location.reload();
          },
          900
        );

      } catch (error) {
        setFrostEditorStatus(
          status,
          error.message,
          true
        );

        saveButton.disabled =
          false;

        cancelButton.disabled =
          false;
      }
    }
  );
}


/* =========================================================
   IMAGE / PLOT UPLOADER
   ========================================================= */

function initFrostImageUploader(
  container
) {
  if (
    container.dataset
      .frostEditorReady
  ) {
    return;
  }

  container.dataset
    .frostEditorReady =
    "true";


  const info =
    frostEditorInfo(
      container
    );


  const row =
    document.createElement(
      "div"
    );

  row.className =
    "frost-editor-row";


  const uploadButton =
    document.createElement(
      "button"
    );

  uploadButton.type =
    "button";

  uploadButton.className =
    "frost-editor-button";

  uploadButton.textContent =
    "+ Add Plot / Image";


  const input =
    document.createElement(
      "input"
    );

  input.type =
    "file";

  input.accept =
    ".png,.jpg,.jpeg," +
    "image/png,image/jpeg";

  input.hidden =
    true;


  const status =
    document.createElement(
      "span"
    );

  status.className =
    "frost-editor-status";


  row.append(
    uploadButton,
    input,
    status
  );

  container.append(
    row
  );


  frostEditorState(
    info
  )
    .then(
      data => {
        if (
          data.images_locked
        ) {
          uploadButton.disabled =
            true;

          uploadButton.textContent =
            "🔒 Image uploads locked";
        }
      }
    )
    .catch(
      () => {}
    );


  uploadButton.addEventListener(
    "click",
    () => {
      input.click();
    }
  );


  input.addEventListener(
    "change",
    async () => {
      const file =
        input.files?.[0];

      if (!file) {
        return;
      }


      uploadButton.disabled =
        true;

      setFrostEditorStatus(
        status,
        `Uploading ${file.name}...`
      );


      const form =
        new FormData();

      form.append(
        "file",
        file
      );


      try {
        const data =
          await frostEditorFetch(
            frostEditorUrl(
              info,
              "image"
            ),
            {
              method: "POST",
              body: form
            }
          );

        setFrostEditorStatus(
          status,
          `Added ${data.filename}. ` +
          "Refreshing..."
        );

        setTimeout(
          () => {
            window.location.reload();
          },
          900
        );

      } catch (error) {
        setFrostEditorStatus(
          status,
          error.message,
          true
        );

        uploadButton.disabled =
          false;

        input.value =
          "";
      }
    }
  );
}

/* =========================================================
   IMAGE DELETE
   ========================================================= */

function initFrostImageDelete(
  container
) {
  if (
    container.dataset
      .frostEditorReady
  ) {
    return;
  }

  container.dataset
    .frostEditorReady =
    "true";


  const info =
    frostEditorInfo(
      container
    );

  const filename =
    container.dataset.filename;


  if (!filename) {
    return;
  }


  const row =
    document.createElement(
      "div"
    );

  row.className =
    "frost-editor-row";


  const deleteButton =
    document.createElement(
      "button"
    );

  deleteButton.type =
    "button";

  deleteButton.className =
    "frost-editor-button " +
    "frost-editor-button--danger";

  deleteButton.textContent =
    "Delete image";


  const status =
    document.createElement(
      "span"
    );

  status.className =
    "frost-editor-status";


  row.append(
    deleteButton,
    status
  );

  container.append(
    row
  );


  /* ---------------------------------------------
     CHECK LOCK
     --------------------------------------------- */

  frostEditorState(
    info
  )
    .then(
      data => {
        if (
          data.images_locked
        ) {
          deleteButton.disabled =
            true;

          deleteButton.textContent =
            "🔒 Image locked";
        }
      }
    )
    .catch(
      () => {}
    );


  /* ---------------------------------------------
     DELETE
     --------------------------------------------- */

  deleteButton.addEventListener(
    "click",
    async () => {

      const confirmed =
        window.confirm(
          `Delete "${filename}"?\n\n` +
          "This removes the image from the " +
          "experiment's source data."
        );


      if (!confirmed) {
        return;
      }


      deleteButton.disabled =
        true;


      setFrostEditorStatus(
        status,
        "Deleting..."
      );


      try {
        await frostEditorFetch(
          frostEditorUrl(
            info,
            "image/" +
            encodeURIComponent(
              filename
            )
          ),
          {
            method: "DELETE"
          }
        );


        setFrostEditorStatus(
          status,
          "Deleted. Refreshing..."
        );


        setTimeout(
          () => {
            window.location.reload();
          },
          900
        );


      } catch (error) {
        setFrostEditorStatus(
          status,
          error.message,
          true
        );

        deleteButton.disabled =
          false;
      }
    }
  );
}

/* =========================================================
   INITIALIZE
   ========================================================= */

function initFrostEditor() {
  document
    .querySelectorAll(
      ".frost-editor-notes"
    )
    .forEach(
      initFrostNotesEditor
    );


  document
    .querySelectorAll(
      ".frost-editor-upload"
    )
    .forEach(
      initFrostImageUploader
    );


  document
    .querySelectorAll(
      ".frost-editor-image-delete"
    )
    .forEach(
      initFrostImageDelete
    );
}


/*
 * Material navigation.instant can replace the
 * page without doing a full browser reload.
 */
if (
  typeof document$
  !== "undefined"
) {
  document$.subscribe(
    function () {
      initFrostEditor();
    }
  );
}


/*
 * Normal first load.
 */
window.addEventListener(
  "DOMContentLoaded",
  initFrostEditor
);