# Anki Flexible Dupe Checing
# Copyright (C) 2019-2020 Matthew Hayes

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import aqt

from aqt import mw
from anki.hooks import wrap
from anki.notes import Note, NoteFieldsCheckResult
from anki.utils import field_checksum, strip_html_media, split_fields
from aqt.editor import Editor
from aqt.operations import QueryOp
from aqt.utils import tr
from anki.collection import SearchNode

# When this is appended to the names of fields, then those fields are considered along with the
# first field when checking for duplicates in the editor.

config = mw.addonManager.getConfig(__name__)
KEYS = config['field_names']

def update_duplicate_display(self, first_field_result, duplicate_fields) -> None:
    cols = [""] * len(self.note.fields)
    cloze_hint = ""
    if first_field_result == NoteFieldsCheckResult.DUPLICATE:
        cols[0] = "dupe"
    elif first_field_result == NoteFieldsCheckResult.NOTETYPE_NOT_CLOZE:
        cloze_hint = tr.adding_cloze_outside_cloze_notetype()
    elif first_field_result == NoteFieldsCheckResult.FIELD_NOT_CLOZE:
        cloze_hint = tr.adding_cloze_outside_cloze_field()

    for field_ord in duplicate_fields:
        cols[field_ord] = "dupe"

    self.web.eval(
        'require("anki/ui").loaded.then(() => {'
        f"setBackgrounds({json.dumps(cols)});\n"
        f"setClozeHint({json.dumps(cloze_hint)});\n"
        "}); "
    )

def check_duplicate(self, _old) -> None:
    note = self.note
    if not note:
        return

    def on_done(result: tuple) -> None:
        first_field_result, duplicate_fields = result
        if self.note != note:
            return
        update_duplicate_display(self, first_field_result, duplicate_fields)

    QueryOp(
        parent=self.parentWindow,
        op=lambda _: note.fields_check(),
        success=on_done,
    ).run_in_background()


def get_primary_key_field_orders(self) -> list:
    note_type = self.note_type()

    field_ords = []
    for fld in note_type["flds"]:
        if fld["name"] in KEYS:
            field_ords.append(fld["ord"])

    return field_ords

def create_search_query(self) -> str:
    nid = self.id
    primary_key_cols = get_primary_key_field_orders(self)
    queries = []

    for order in primary_key_cols:
        if not self.fields[order].strip():
            continue
        val = self.fields[order]
        for name in KEYS:
            queries.append("\"%s:%s\"" % (name, val))

    return "-nid:%s (%s)" % (nid, " OR ".join(queries)) if len(queries) != 0 else ""

def is_duplicate(self, _old) -> tuple:
    cols = get_primary_key_field_orders(self)
    orders = []

    query = create_search_query(self)
    if query != "":
        for order in cols:
            if len(self.col.find_cards(create_search_query(self))) != 0:
                orders.append(order)

    return _old(self), orders


def show_dupes(self, _old) -> None:
    note = self.note
    if not note:
        return

    query = create_search_query(note)

    browser = aqt.dialogs.open("Browser", self.mw)
    browser.form.searchEdit.lineEdit().setText(query)
    browser.onSearchActivated()

def setup():
    print("Setting up duplicate checking...")
    Editor._check_and_update_duplicate_display_async = wrap(Editor._check_and_update_duplicate_display_async, check_duplicate, "around")
    Note.fields_check = wrap(Note.fields_check, is_duplicate, "around")
    Editor.showDupes = wrap(Editor.showDupes, show_dupes, "around")
    # Editor._links["dupes"] = showDupes
