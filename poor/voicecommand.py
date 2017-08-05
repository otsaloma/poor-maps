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

__all__ = ("Narrative",)

class VoiceCommand:

    """Voice command generator"""

    def __init__(self):
        """Initialize a :class:`VoiceCommand` instance."""
        self.tmpdir = None
        self.engine = "espeak"
        self.voice = "en" ### TODO, hook languages and argument
        self.previous_command = None
        self.tmpdir = tempfile.mkdtemp(prefix="poor-maps-")

    def __del__(self):
        if self.tmpdir:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None
            self.previous_command = None

    def clear_command(self):
        if self.previous_command:
            os.remove(self.previous_command)
            self.previous_command = None

    def command(self, cmd):
        self.clear_command()
        self.previous_command = tempfile.mktemp(suffix=".wav", dir = self.tmpdir)

        if self.engine == "espeak":
            with open(self.previous_command, "w") as f:
                if subprocess.call(['espeak', '--stdout', cmd], stdout=f) != 0:
                    self.previous_command = None
        else:
            # unknown engine
            self.previous_command = None
        return self.previous_command

