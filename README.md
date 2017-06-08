Alfred MPD
==========

Control MPD from [Alfred][alfred].

![][screenshot]


Installation
------------

Download the latest version from [GitHub releases][gh-releases].


Usage
-----

- `mpd [<query>]` — View mpd status and search for tracks
    - On actions:
        - `↩` or `⌘+<NUM>` — Perform action
    - On tracks:
        - `↩` or `⌘+<NUM>` — Queue track
        - `⌘+↩` — Play track
        - `⌥+↩` — Clear queue and play track
        - `^+↩` — Queue album
    - On albums/artists/playlists/types:
        - `↩`, `⇥` or `⌘+<NUM>` — Search within albums/artists/playlists/types


Licencing, thanks
-----------------

This workflow is released under the [MIT licence][mit].

It is based on the [Alfred-Workflow][aw] library, which is also released under the [MIT licence][mit].

The icons are from [Elusive Icons][elusive], [Font Awesome][awesome] and [Material Design][material].


Changelog
---------

### 0.1.0 ###

- First release

### 0.1.1 ###

- Fix broken build


[mit]: ./src/LICENCE.txt
[aw]: http://www.deanishe.net/alfred-workflow/
[alfred]: https://alfredapp.com
[screenshot]: ./screenshot.png
[gh-releases]: https://github.com/deanishe/alfred-mpd/releases/latest
[elusive]: https://github.com/aristath/elusive-iconfont
[awesome]: http://fortawesome.github.io/Font-Awesome/
[material]: http://zavoloklom.github.io/material-design-iconic-font/

