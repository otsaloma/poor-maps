# -*- coding: utf-8 -*-

# Copyright (C) 2016 Osmo Salomaa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Internationalization functions."""

import gettext
import locale
import poor

_translation = gettext.translation(
    "poor-maps",
    localedir=poor.LOCALE_DIR,
    languages=[locale.getdefaultlocale()[0] or ""],
    fallback=True)

_foreign_translations = {}

def _(message):
    """Return the localized translation of `message`."""
    return _translation.gettext(message)

def __(message, language):
    """Return the translation of `message` to `language`. Note that the same
    notation is used for languages, as in the voice module"""
    # exceptions
    l = {
        "de": "de_DE",
        "en": "en_US",
        "en-US": "en_US",
        "en-US-x-pirate": "en_US",
        "es": "es_ES",
        }

    lang = l.get(language, language)
    if not lang in _foreign_translations:
        _foreign_translations[lang] = gettext.translation( "poor-maps",
                                                           localedir=poor.LOCALE_DIR,
                                                           languages=lang,
                                                           fallback=True )
    return _foreign_translations[lang].gettext(message)
