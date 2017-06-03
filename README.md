Alfred MPD
==========

Control MPD from [Alfred][alfred].

![][screenshot]


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


Changelog
---------

### 0.1.0 ###

- First release


[mit]: ./src/LICENCE.txt
[aw]: http://www.deanishe.net/alfred-workflow/
[alfred]: https://alfredapp.com
[screenshot]: ./screenshot.png
