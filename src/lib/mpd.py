#!/usr/bin/env python
# encoding: utf-8
#
# Copyright (c) 2017 Dean Jackson <deanishe@deanishe.net>
#
# MIT Licence. See http://opensource.org/licenses/MIT
#
# Created on 2017-03-13
#

"""
"""

from __future__ import print_function, absolute_import

from collections import namedtuple
import logging
import os
import re
import subprocess
import time


MPC = os.getenv('MPC') or 'mpc'
MPD_HOST = os.getenv('MPD_HOST') or 'localhost'
MPD_PORT = os.getenv('MPD_PORT') or '6600'

# The maximum number of track that will be read from MPD
# Set to 0 to fetch all results
MAX_RESULTS = 0

# The "wire" format for tracks. This includes all the metadata
# the workflow needs.
#
# Unicode characters:
#
#   \U000000A0      non-breaking space
#   \U0001F389      party popper
#   \U0000266A      eighth note

# DELIMITER = u'\U000000A0\U0001F389\U000000A0'  # party popper
DELIMITER = u'\U000000A0\U0000266A\U000000A0'  # eighth note
RESULT_FORMAT = (u'%artist%{0}%album%{0}%disc%{0}'
                 u'%track%{0}%title%{0}%file%'.format(DELIMITER))

log = logging.getLogger('workflow.{}'.format(__name__))


class MPDError(Exception):
    """Base exception for problems with MPD."""

    def __init__(self, msg, reason=''):
        """Create a new MPD error."""
        super(MPDError, self).__init__()
        self.msg = msg
        self.reason = reason


class CommandFailed(MPDError):
    """Raised if MPD doesn't like the input."""
    def __init__(self, msg, cmd, reason=''):
        """Create a new MPD error."""
        super(CommandFailed, self).__init__(msg, reason)
        self.cmd = cmd


class ConnectionError(MPDError):
    """Raised if a connection can't be established."""


class InvalidType(MPDError):
    """Raised if an invalid type is specified."""

    def __init__(self, err):
        """Create a new errror."""
        bad, valid = self._parse_err(err)
        super(InvalidType, self).__init__(
            'Invalid search type',
            '"{}" is not a valid type. Choose from {}'.format(bad, valid))
        self.what = bad
        self.valid = valid

    @staticmethod
    def _parse_err(err):
        """Parse the server error message into bad and valid types."""
        m = re.match(r'"(.*?)" is not a valid search type: <(.+)>', err)
        if not m:
            raise ValueError('could not parse MPD error : {!r}'.format(err))

        bad, valid = m.groups()
        return bad, tuple(valid.split('|'))


# Data models returned by this module
Stats = namedtuple('Stats', 'artists albums songs')
Status = namedtuple('Status', 'track playing index total')
Track = namedtuple('Track', 'artist album disc track title file')


def _stringify(obj):
    """Turn ``obj`` into a string for `Popen`."""
    if isinstance(obj, str):
        return obj

    if isinstance(obj, unicode):
        return obj.encode('utf-8')

    return str(obj)


def _parse_error_msg(err):
    """Parse MPD error message."""
    if not err.startswith('mpd error:'):
        return err
    return err.split(':', 1)[1].strip()


def _parse_track_list(out):
    """Parse `mpc` output into a list of `Track` tuples."""
    tracks = []
    lines = out.splitlines()
    for i, line in enumerate(lines):
        tracks.append(Track(*line.split(DELIMITER)))
        if MAX_RESULTS and i >= MAX_RESULTS - 1:
            log.debug('truncated results to %d/%d', MAX_RESULTS, len(lines))
            break

    return tracks


def mpc(command, args=None, opts=None):
    """Execute ``mpc`` and return output."""
    args = [_stringify(s) for s in args or []]
    opts = [_stringify(s) for s in opts or []]
    cmd = [MPC, '--host', MPD_HOST, '--port', MPD_PORT] \
        + opts \
        + [_stringify(command)] \
        + args

    log.debug('cmd=%r', cmd)

    start = time.time()

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # MPD uses UTF-8 only
    out, err = [s.decode('utf-8') for s in p.communicate()]
    err = _parse_error_msg(err)

    elapsed = time.time() - start

    if p.returncode:
        # Raise custom errors
        if err == u'Connection refused':
            raise ConnectionError(
                "Can't connect to MPD",
                "Are your host & port settings correct? Is MPD running?")

        if 'is not a valid search type' in err:
            raise InvalidType(err)

        log.error('command failed: %s', err)

        raise CommandFailed('MPD error ({})'.format(p.returncode), cmd, err)

    # log.debug('------------- STDOUT -------------')
    # log.debug(out)
    # if err:
    #     log.debug('------------- mpc error -------------')
    #     log.debug(err)
    # log.debug('-------------------------------------')

    log.debug('Finished in %0.2fs', elapsed)

    return out


def mpctracks(command, args=None):
    """Fetch a list of `Track` tuples from MPD."""
    out = mpc(command, args, ('-f', RESULT_FORMAT))
    return _parse_track_list(out)


def current():
    """Fetch current track."""
    tracks = mpctracks('current')
    if not tracks:
        return None

    return tracks[0]


def version():
    """Fetch MPD API version."""
    # sample output:
    # mpd version: 0.20.0
    s = mpc('version')
    return s.split(':')[-1].strip()


def queue():
    """Retrieve tracks in queue."""
    return mpctracks('playlist')


def playing():
    """Retrieve playback status."""
    return status().playing


def playlists():
    """Fetch lists of available playlists."""
    return mpc('lsplaylists').splitlines()


def _parse_query(query):
    """Parse ``type:query`` elements in type & query pairs."""
    if ':' not in query:
        return ['any', query]

    pairs = []
    for word in query.split():
        if ':' in word:
            pairs.append(word.split(':'))
        else:
            pairs.append((None, word))

    args = []
    typ = None
    for t, w in pairs:
        if t:
            args.append(t)
        elif not typ:
            args.append('any')
            typ = 'any'
        args.append(w)

    log.debug('query=%r, mpc=%r', query, args)
    return args


def search(query):
    """Retrieve matching tracks."""
    args = _parse_query(query)
    return mpctracks('search', args)


def find(query):
    """Retrieve *exactly* matching tracks."""
    args = _parse_query(query)
    return mpctracks('find', args)


def types():
    """Fetch list of valid search types."""
    # mpc doesn't appear to provide a list, so provoke an
    # InvalidType error by sending an invalid type.
    try:
        search('whereverwhenever:shakira!')
    except InvalidType as exc:
        return exc.valid


def stats():
    """Fetch statistics about MPD library."""
    artists = 0
    albums = 0
    songs = 0

    for line in mpc('stats').splitlines():
        if u':' not in line:
            continue

        key, val = [s.strip() for s in line.split(u':', 1)]
        if key == u'Artists':
            artists = int(val)
        elif key == u'Albums':
            albums = int(val)
        elif key == u'Songs':
            songs = int(val)

    return Stats(artists, albums, songs)


def status():
    """Retrieve MPD status inc. playing/paused and volume."""
    out = mpc('status', opts=('-f', RESULT_FORMAT))
    for i, line in enumerate(out.splitlines()):
        log.debug(u'status %d: %s', i, line)
        m = re.match(r"""
            \[([a-z]+)\]\s+         # playback status
            \#(\d+)/(\d+)\s+        # playlist position
            .+
            \((\d+)%\)              # progress
            .*                      # anything else
            """, line, re.VERBOSE)
        if m:
            mode, pos, count, pc = m.groups()
            pos, count, pc = [int(s) for s in (pos, count, pc)]
            log.debug('mode=%r, pos=%r, count=%r, pc=%r', mode, pos, count, pc)
        elif i == 0:  # assume title of current track
            t = _parse_track_list(line)
            log.debug('current track=%r', t)

    cur = current()
    return Status(cur, mode == 'playing', pos, count)


def playpause():
    """Start/stop playback."""
    if playing():
        mpc('pause')
    else:
        # TODO: check if there are tracks to play?
        mpc('play')


def queue_track(track):
    """Add a `Track` to the queue."""
    out = mpc('add', (track.file,))
    log.debug('out=%r', out)


# TODO: play+pause
# TODO: play track (use queue, or add then play)
# TODO: queue
# TODO: unqueue
# TODO: queue album
# TODO: clear
# TODO: previous
# TODO: next

# TODO: outputs
