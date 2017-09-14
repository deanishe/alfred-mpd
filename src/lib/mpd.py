#!/usr/bin/env python
# encoding: utf-8
#
# Copyright (c) 2017 Dean Jackson <deanishe@deanishe.net>
#
# MIT Licence. See http://opensource.org/licenses/MIT
#
# Created on 2017-03-13
#

"""Wrapper around the `mpc` command-line client for `mpd`."""

from __future__ import print_function, absolute_import

from collections import namedtuple, OrderedDict
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
Status = namedtuple('Status', 'track playing index total volume')
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
    command = _stringify(command)
    args = [_stringify(s) for s in args or []]
    opts = [_stringify(s) for s in opts or []]
    cmd = [MPC, '--host', MPD_HOST, '--port', MPD_PORT] \
        + opts \
        + [command] \
        + args

    log.debug('mpc command: %s', [command] + args)

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


def version():
    """Fetch MPD API version."""
    # sample output:
    # mpd version: 0.20.0
    s = mpc('version')
    return s.split(':')[-1].strip()


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
    q = u''
    for t, w in pairs:
        if t:
            if q:
                args.append(q)
                q = u''

            args.append(t)
            typ = t

        elif not typ:
            args.append('any')
            typ = 'any'

        q = u'{} {}'.format(q, w).strip()
        # args.append(w)
    args.append(q)

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


_match_playback_status = re.compile(r"""
    \[([a-z]+)\]\s+         # playback status
    \#(\d+)/(\d+)\s+        # playlist position
    .+
    \((\d+)%\)              # progress
    .*                      # anything else
    """, re.VERBOSE).match

_find_playback_settings = re.compile(r'(\w+): ?([0-9%ofn/a]+)').findall


def _parse_status(out):
    """Parse ``mpc`` status response returned by many commands."""
    mode = 'stopped'
    pos = count = pc = volume = 0
    cur = None

    for i, line in enumerate(out.splitlines()):
        log.debug('status: %r', line)

        m = _match_playback_status(line)
        if m:  # playback status
            mode, pos, count, pc = m.groups()
            pos, count, pc = [int(s) for s in (pos, count, pc)]
            log.debug('mode=%r, pos=%r, count=%r, pc=%r', mode, pos, count, pc)

        elif line.startswith('volume'):  # playback settings
            for k, v in _find_playback_settings(line):
                if k == 'volume':
                    if v.strip() == 'n/a':  # hardware decoder
                        volume = 'n/a'
                    else:
                        volume = int(v.rstrip('%'))
                    log.debug('volume=%r', volume)

        elif DELIMITER in line:  # current track
            # log.debug('current track: %r', line)
            cur = _parse_track_list(line)[0]
            log.debug('current track=%r', cur)

    return Status(cur, mode == 'playing', pos, count, volume)


def artists(query=None):
    """List/search artists."""
    artists = OrderedDict()
    if query:
        out = mpc('search',
                  ['artist', query],
                  ('-f', '%artist%')).strip()
    else:
        out = mpc('list', ['artist']).strip()

    if not out:
        return []

    results = out.split('\n')

    log.debug('results=%r', results)
    for name in results:
            artists[name] = True

    return artists.keys()


def albums(query=None):
    """List/search all artists."""
    albums = OrderedDict()
    if query:
        out = mpc('search',
                  ['album', query],
                  ('-f', '%album%')).strip()
    else:
        out = mpc('list', ['album']).strip()

    if not out:
        return []

    results = out.split('\n')

    log.debug('results=%r', results)
    for name in results:
            albums[name] = True

    return albums.keys()


def status():
    """Retrieve MPD status inc. playing/paused and volume."""
    out = mpc('status', opts=('--format', RESULT_FORMAT))
    return _parse_status(out)


def queue():
    """Retrieve tracks in queue."""
    return mpctracks('playlist')


def clear():
    """Clear queue."""
    mpc('clear')


def update():
    """Rescan media for changes."""
    mpc('update')


def current():
    """Fetch current track."""
    tracks = mpctracks('current')
    if not tracks:
        return None

    return tracks[0]


def playing():
    """Retrieve playback status."""
    return status().playing


def playpause():
    """Start/stop playback."""
    if playing():
        mpc('pause')
        log.info('playback paused')
    else:
        # TODO: check if there are tracks to play?
        c = current()
        q = queue()
        log.debug('current=%r, %d tracks in queue', c, len(q))
        mpc('play')
        log.info('playback started')


def play(index=None):
    """Start playback."""
    args = [index] if index else []
    out = mpc('play', args)
    log.info('playback started')
    return _parse_status(out)


def play_playlist(name):
    """Play a playlist."""
    mpc('load', [name])


def stop():
    """Stop playback."""
    out = mpc('stop')
    log.info('playback stopped')
    return _parse_status(out)


def queue_track(track):
    """Add a `Track` to the queue."""
    mpc('add', (track.file,))
    log.info('track queued: %s', track.file)


def remove_track(track):
    """Remove a `Track` from the queue."""
    idx = 0
    for i, t in enumerate(queue()):
        idx += 1
        if t.file == track.file:
            mpc('del', (idx,))
            idx -= 1
            log.info('track removed: %s', track.file)


def skip_next():
    """Go to next track."""
    out = mpc('next')
    log.debug('out=%r', out)
    log.info('skipped to next track')


def skip_previous():
    """Go to previous track."""
    out = mpc('prev')
    log.debug('out=%r', out)
    log.info('skipped to previous track')


def _setvol(v):
    """Set volume to ``v``."""
    out = mpc('volume', (v,))
    st = _parse_status(out)
    log.info('volume set to %d%%', st.volume)
    return st


def mute():
    """Set volume to 0."""
    return _setvol('0')


def volume_up():
    """Increase volume."""
    return _setvol('+10')


def volume_down():
    """Decrease volume."""
    return _setvol('-10')
