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

"""Voice directions support"""

import copy
import os
import poor
import re
import shutil
import subprocess
import tempfile
import threading
import queue

import poor.util

##############################################################################
class Voice:
    """Helper class to store file name of the voice direction and the corresponding time moment"""

    def __init__(self, filename = None, time = None):
        self.filename = filename
        self.time = time

##############################################################################
# Base class for voice engines responsible for converting text to WAV
# file
##############################################################################
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
            return next (iter (a.values()))
        return None

    def set_voice(self, language, sex = "male"):
        """Set the voice used for WAV file generation"""
        self.voice_name = self._get_voice_name(language, sex)


##############################################################################
# Base class for voice engines that process some words in en-US-x-pirate and
# replace them with SSML phonemes
##############################################################################
class VoiceEngineEnUsPirate(VoiceEngineBase):

    """Base class used by mimic and flite-based voice engines for en-US-x-pirate locale"""

    def __init__(self):
        self.phonemes = { "Arrr": "aa r ah0 r r .",
                          "Cap'n": "k ae1 p n",
                          "head'n": "hh eh1 d ah0 n",
                          "th'": "dh" }

    def process_text(self, text):
        # preprocess to catch few words in Pirate's dictionary
        for word, ph in self.phonemes.items():
            if word == "th'":
                text = text.replace(" %s " % word, ' <phoneme ph="%s">phonemes-given</phoneme> ' % ph)
            else:
                text = re.sub(r"\b%s\b" % word, '<phoneme ph="%s">phonemes-given</phoneme>' % ph, text)
        return text        


##############################################################################
### Specific voice engines
##############################################################################
#
# Voice engine has to fill in
#
# * language dictionary with the voices
# * command that can be checked for existing executable
#
# and provide make_wav method.

##############################################################################
class VoiceEngineMimic(VoiceEngineBase):

    """Interface to mimic"""

    def __init__(self):
        VoiceEngineBase.__init__(self)
        self.languages = {
            "en": { "male": "ap", "female": "slt" },
            "en-US": { "male": "ap", "female": "slt" },
        }
        self.set_command(["mimic", "harbour-mimic"])

    def make_wav(self, text, fname):
        """Create a new WAV file specified by fname with the specified text
        using given language and, if possible, sex"""
        return subprocess.call([self.command,
                                '-t', text,
                                '-o', fname,
                                '-voice', self.voice_name]) == 0

class VoiceEngineMimicEnUsPirate(VoiceEngineEnUsPirate):

    """Interface to mimic using SSML for tricky pronunciations for en-US-x-pirate locale"""

    def __init__(self):
        VoiceEngineBase.__init__(self)
        VoiceEngineEnUsPirate.__init__(self)
        self.languages = {
            # don't use ap voice since it has issues with SSML phoneme
            "en-US-x-pirate": { "male": "awb", "female": "slt" }
        }
        self.set_command(["mimic", "harbour-mimic"])

    def make_wav(self, text, fname):
        """Create a new WAV file specified by fname with the specified text
        using given language and, if possible, sex"""
        text = self.process_text(text)
        return subprocess.call([self.command,
                                '-ssml',
                                '-t', text,
                                '-o', fname,
                                '-voice', self.voice_name]) == 0

##############################################################################
class VoiceEngineFlite(VoiceEngineBase):

    """Interface to flite"""

    def __init__(self):
        VoiceEngineBase.__init__(self)
        self.languages = {
            "en": { "male": "kal16", "female": "slt" },
            "en-US": { "male": "kal16", "female": "slt" },
        }
        self.set_command(["flite", "harbour-flite"])

    def make_wav(self, text, fname):
        """Create a new WAV file specified by fname with the specified text
        using given language and, if possible, sex"""
        return subprocess.call([self.command,
                                '-t', text,
                                '-o', fname,
                                '-voice', self.voice_name]) == 0

class VoiceEngineFliteEnUsPirate(VoiceEngineEnUsPirate):

    """Interface to flite using SSML for tricky pronunciations for en-US-x-pirate locale"""

    def __init__(self):
        VoiceEngineBase.__init__(self)
        VoiceEngineEnUsPirate.__init__(self)
        self.languages = {
            # don't use ap voice since it has issues with SSML phoneme
            "en-US-x-pirate": { "male": "awb", "female": "slt" }
        }
        self.set_command(["flite", "harbour-flite"])

    def make_wav(self, text, fname):
        """Create a new WAV file specified by fname with the specified text
        using given language and, if possible, sex"""
        text = self.process_text(text)
        return subprocess.call([self.command,
                                '-ssml',
                                '-t', text,
                                '-o', fname,
                                '-voice', self.voice_name]) == 0

##############################################################################
class VoiceEnginePicoTTS(VoiceEngineBase):

    """Interface to PicoTTS"""

    def __init__(self):
        VoiceEngineBase.__init__(self)
        self.languages = {
            "de": { "female": "de-DE" },
            "en": { "female": "en-US" },
            "en-GB": { "female": "en-GB" },
            "en-US": { "female": "en-US" },
            "en-US-x-pirate": { "female": "en-US" },
            "es": { "female": "es-ES" },
            "fr": { "female": "fr-FR" },
            "it": { "female": "it-IT" }
        }
        self.set_command(["pico2wave", "harbour-pico2wave"])

    def make_wav(self, text, fname):
        """Create a new WAV file specified by fname with the specified text
        using given language and, if possible, sex"""
        return subprocess.call([self.command,
                                '-w', fname,
                                '-l', self.voice_name,
                                text]) == 0

##############################################################################
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
            "fr": { "male": "french" },
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

##############################################################################
# Worker thread run function
def voice_worker(queue_tasks, queue_results, engine, tmpdir):
    while True:
        cmd = queue_tasks.get()
        if cmd is None:
            break
        fname = tempfile.mktemp(suffix=".wav", dir = tmpdir)
        if not engine.make_wav( cmd, fname ):
            fname = None
        queue_results.put( (cmd, fname) )
        queue_tasks.task_done()

##############################################################################
# Interface to available voice engines
class VoiceDirection:

    """Voice direction generator"""

    def __init__(self):
        """Initialize a :class:`VoiceDirection` instance."""
        self.tmpdir = None
        # fill engines in the order of preference
        self.engines = [ VoiceEngineMimic(), VoiceEngineMimicEnUsPirate(),
                         VoiceEngineFlite(), VoiceEngineFliteEnUsPirate(),
                         VoiceEnginePicoTTS(), VoiceEngineEspeak() ]
        self.engine = None
        self.tmpdir = tempfile.mkdtemp(prefix="poor-maps-")
        self.worker_thread = None
        self.queue_tasks = None
        self.queue_results = None
        self.cache = {}
        self.last_cache_check_time = 0

    def __del__(self):
        self._clean_worker()

        if self.tmpdir:
            shutil.rmtree(self.tmpdir)
            self.tmpdir = None
            self.previous_command = None

    def _clean_worker(self):
        if self.worker_thread is not None:
            self.queue_tasks.put(None)
            self.worker_thread.join()
            self.worker_thread = None
            self._update_cache() # to ensure that we have all items

    def _clean_cache(self):
        for cmd, voice in self.cache.items():
            if voice.filename is not None:
                os.remove(voice.filename)
        self.cache = {}

    def clean(self):
        """Stop the worker and clean the cache"""
        self._clean_worker()
        self._clean_cache()
        self.last_cache_check_time = 0
        #print("Voice engine cleaned")

    def active(self):
        """True when TTS engine is selected"""
        return self.engine is not None

    def set_voice(self, language, sex = "male"):
        """Find the engine that matches requested language and, if that engine
        supports, prefer the requested sex"""
        #print("Voice requested:", language, sex)
        self.clean()
        if language is None:
            self.engine = None
        else:
            for e in self.engines:
                if e.supports(language):
                    self.engine = e
                    self.engine.set_voice(language, sex)
                    return
        self.engine = None

    def make(self, cmd, time):
        """Request to generate voice for cmd, expected at given time from destination"""
        if self.engine is None:
            return
        self._update_cache()
        if cmd in self.cache:
            if self.cache[cmd].time > time:
                self.cache[cmd].time = time
            return

        if self.worker_thread is None:
            self.queue_tasks = queue.Queue()
            self.queue_results = queue.Queue()
            self.worker_thread = threading.Thread( target = voice_worker,
                                                   kwargs = {'queue_tasks': self.queue_tasks,
                                                             'queue_results': self.queue_results,
                                                             'engine': self.engine,
                                                             'tmpdir': self.tmpdir } )
            self.worker_thread.start()

        # add an empty element into cache to ensure that we don't
        # run the same voice direction twice through the engine
        self.cache[cmd] = Voice(time=time)
        self.queue_tasks.put(cmd)
        #print("Request", cmd, time)

    def get(self, cmd):
        """Get the voice for the direction"""
        self._update_cache()
        voice = self.cache.get(cmd, None)
        #print("Wanted:", cmd, vars(voice))
        if voice is not None:
            return voice.filename
        return None

    def _update_cache(self):
        """Update the cache"""
        if self.queue_results is None:
            return
        while not self.queue_results.empty():
            cmd, fname = self.queue_results.get_nowait()
            self.queue_results.task_done()
            self.cache[cmd].filename = fname # time is already set
            #print("Got", cmd)

    def set_time(self, time):
        """Checks the cache for expiry. Note that the time is relative to destination"""
        if abs(time - self.last_cache_check_time) < 600:
            return
        self.last_cache_check_time = time
        keys = [k for k, v in self.cache.items() if v.time - time > 600]
        for k in keys:
            voice = self.cache[k]
            if voice.filename is not None:
                os.remove(voice.filename)
            #print("Delete", k)
            del self.cache[k]
