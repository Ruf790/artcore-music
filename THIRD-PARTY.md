# Third-party components

ArtCore Music is distributed under the GNU General Public License v3 (see LICENSE).
It contains the following components:

| Component | What for | License |
|---|---|---|
| [mpv](https://mpv.io) — `libmpv-2.dll`, Windows build by [shinchiro/mpv-winbuild-cmake](https://github.com/shinchiro/mpv-winbuild-cmake) | playback engine | GPL v2+ (this build), parts LGPL |
| [FFmpeg](https://ffmpeg.org) and other libraries inside libmpv | decoding, audio filters | GPL / LGPL |
| [Qt 6](https://www.qt.io) via [PySide6](https://pypi.org/project/PySide6/) | user interface | LGPL v3 |
| [python-mpv](https://github.com/jaseg/python-mpv) | Python binding for libmpv | GPL v2+ or LGPL v2.1+ |
| [mutagen](https://github.com/quodlibet/mutagen) | tags and cover art | GPL v2+ |
| [QtAwesome](https://github.com/spyder-ide/qtawesome) | icons | MIT |
| [Font Awesome Free](https://fontawesome.com), [Material Design Icons](https://pictogrammers.com) (inside QtAwesome) | icon fonts | SIL OFL 1.1 / Apache 2.0 |
| Python | runtime | PSF License |

The source code of mpv and of the libraries it is built from is available from the projects above;
the exact libmpv build used is named in the build log (`tools/fetch_libmpv.py`).
