# -*- coding: utf-8 -*-

# Copyright (C) 2017 Osmo Salomaa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Voice command support"""

import os
import poor
import shutil
import subprocess
import tempfile

import poor.util

class VoiceEngineBase:

    """Base class for voice engines. Provides methods that allow to test
    whether requested language is supported and set the voice name
    based on the disctionary filled by the objects from descending
    classes.
    """

    def __init__(self):
        self.languages = {}
        self.voice_name = None
        self.command = None

    def set_command(self, cmds):
        """Set command for this engine from the list of possible commands"""
        for cmd in cmds:
            if poor.util.requirement_found(cmd):
                self.command = cmd
                return
        
    def supports(self, language):
        """Return true if the engine supports the requested language"""
        return self.command is not None and language in self.languages

    def _get_voice_name(self, language, sex):
        if language in self.languages:
            a = self.languages[language]
            if sex in a:
                return a[sex]
            return a[ a.keys[0] ]
        return None

    def set_voice(self, language, sex = "male"):
        """Set the voice used for WAV file generation"""
        self.voice_name = self._get_voice_name(language, sex)

#######################################
### Specific voice engines
#######################################
#
# Voice engine has to fill in
#
# * language dictionary with the voices
# * command that can be checked for existing executable
#
# and provide make_wav method.

#######################################
class VoiceEngineFlite(VoiceEngineBase):

    """Interface to flite"""

    def __init__(self):
        VoiceEngineBase.__init__(self)
        self.languages = {
            "en": { "male": "kal16", "female": "slt" },
            "en-US": { "male": "kal16", "female": "slt" },
            "en-US-x-pirate": { "male": "awb" }
        }
        self.set_command(["flite", "harbour-flite"])

    def make_wav(self, text, fname):
        """Create a new WAV file specified by fname with the specified text
        using given language and, if possible, sex"""
        return subprocess.call([self.command,
                                '-t', text,
                                '-o', fname,
                                '-voice', self.voice_name]) == 0

#######################################
class VoiceEngineEspeak(VoiceEngineBase):

    """Interface to espeak"""

    def __init__(self):
        VoiceEngineBase.__init__(self)
        self.languages = {
            "ca": { "male": "catalan" },
            "cz": { "male": "czech" },
            "de": { "male": "german" },
            "en": { "male": "english-us" },
            "en-US": { "male": "english-us" },
            "en-US-x-pirate": { "male": "en-scottish" },
            "es": { "male": "spanish" },
            "hi": { "male": "hindi" },
            "it": { "male": "italian" },
            "ru": { "male": "russian_test" },
            "sl": { "male": "slovak" },
            "sv": { "male": "swedish" }
        }
        self.set_command(["espeak", "harbour-espeak"])

    def make_wav(self, text, fname):
        """Create a new WAV file specified by fname with the specified text
        using given language and, if possible, sex"""
        with open(fname, "w") as f:
            result = (subprocess.call([self.command, '--stdout',
                                       '-v', self.voice_name,
                                       text], stdout=f) == 0)
        return result
    
class VoiceCommand:

    """Voice command generator"""

    def __init__(self):
        """Initialize a :class:`VoiceCommand` instance."""
        self.tmpdir = None
        # fill engines in the order of preference
        self.engines = [ VoiceEngineFlite(), VoiceEngineEspeak() ]
        self.engine = None
        self.previous_command = None
        self.tmpdir = tempfile.mkdtemp(prefix="poor-maps-")

    def __del__(self):
        if self.tmpdir:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None
            self.previous_command = None

    def active(self):
        return self.engine is not None

    def set_voice(self, language, sex = "male"):
        if language is None:
            self.engine = None
        else:
            for e in self.engines:
                if e.supports(language):
                    self.engine = e
                    self.engine.set_voice(language, sex)
                    return
        self.engine = None

    def clear_command(self):
        if self.previous_command:
            os.remove(self.previous_command)
            self.previous_command = None

    def command(self, cmd):
        if self.engine is None:
            return None
        self.clear_command()
        self.previous_command = tempfile.mktemp(suffix=".wav", dir = self.tmpdir)
        if not self.engine.make_wav( cmd, self.previous_command ):
            self.previous_command = None
        return self.previous_command

