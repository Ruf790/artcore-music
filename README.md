# ArtCore Music

Аудиоплеер для Windows на движке **mpv** (libmpv) с интерфейсом на Qt. Третья программа семейства ArtCore — рядом с ArtCore Client и [ArtCore Player](https://github.com/Ruf790/artcore-player).

*An audio player for Windows on the mpv engine with a Qt interface. English below.*

## Возможности

- **Форматы:** MP3, FLAC (до 24/192), ALAC, AAC, Opus, Ogg Vorbis, WAV, APE, WavPack, DSD (DSF/DFF), WMA, TAK, TTA, Musepack; многоканальные FLAC/WAV/DSD, AC-3, E-AC-3, DTS, DTS-HD MA, TrueHD.
- **CUE-образы альбомов**: разбивка на треки (кодировки UTF-8 и cp1251, встроенный CUESHEET во FLAC/APE/WavPack); переход между треками образа без перезагрузки и без паузы.
- **5.1**: многоканальный PCM через WASAPI на устройство по умолчанию (или выбранное). Каналы: «как в Windows», «всегда 5.1» (7.1 сводится в 5.1) или стерео. Уровни **центра** и **сабвуфера**, расширение стерео до 5.1 (по желанию), **тест колонок** (розовый шум в каждой колонке по очереди).
- **Индикатор формата**: `FLAC 24/96 5.1 → PCM 6 кан.` — что в файле и что уходит в Windows.
- **Звук:** 10-полосный эквалайзер с пресетами, ReplayGain (по треку / альбому, предусиление, защита от перегрузки), **gapless**, **плавный переход** (crossfade, 1–12 с; внутри одного альбома можно оставить gapless).
- **Обложки и теги:** из тегов (ID3, Vorbis, MP4, APEv2) или `cover.jpg` / `folder.jpg` / `front.jpg` рядом с файлом; исполнитель, альбом, год, номер трека.
- **Плейлист:** папки (рекурсивно), перетаскивание, перестановка мышью, поиск, сортировка, повтор (трек / всё), перемешивание, `.m3u` / `.m3u8` (открыть и сохранить). Плейлист, трек и место в треке возвращаются при следующем запуске.
- **Плейлисты во вкладках**, очередь «Играть следующим», ★ избранное и «Недавно играли», волна трека вместо полосы перемотки (у интернет-радио — живая волна того, что звучит сейчас), **тексты песен** (`.lrc` с подсветкой строки, `.txt` или из тегов), **редактор тегов** (в том числе для многих файлов и из имени файла), **интернет-радио** (`.pls`, `.m3u`, ссылки; «сейчас в эфире»).
- **Удобство:** карточка Windows с обложкой и ⏮ ⏯ ⏭ (над громкостью и на экране блокировки), мини-плеер поверх окон (карточка или полоска, полупрозрачный, с волной), уровни по каналам 5.1 (под обложкой и вид комнаты — V), медиаклавиши клавиатуры (и в фоне), кнопки ⏮ ⏯ ⏭ в превью на панели задач, трей, таймер сна, горячие клавиши (F1 — список), RU / EN, **скины**: тёмный ArtCore и восемь светлых — Светлый, Бумага, Мята, Сакура, Небо, Лаванда, Персик, Снег (меню ☰ → Скин или Настройки; применяется сразу).
- **Цвета от обложки:** волна, кнопка ▶, играющая строка, уровни и мягкий отсвет за обложкой берут цвета альбома (выключается в Настройках).
- **Группы в плейлисте:** у альбома шапка с обложкой, исполнителем, годом, форматом, числом треков и временем; радиостанции и отдельные треки — своими группами; щелчок по шапке сворачивает группу. При поиске — обычный список.
- **Установщик:** «Открыть с помощью» для аудиофайлов, `.cue`, `.m3u`, `.pls` — у каждого формата своя иконка; регистрация в Settings → Apps → Default apps; пункты «Воспроизвести / Добавить в ArtCore Music» в меню папок. Автообновление с GitHub Releases. Есть portable-версия.

## Настройка 5.1 (Sound Blaster Z + DTS Connect)

1. Settings → System → Sound → **Speakers (Sound Blaster Z)** → сделать устройством по умолчанию.
2. Control Panel → Sound → Speakers → **Configure** → **5.1 Surround**.
3. В Sound Blaster Control Panel включить **DTS Connect** (карта кодирует 6 каналов PCM в DTS и отдаёт по оптике).
4. В ArtCore Music: **Звук → Каналы** — «Как в Windows» или «Всегда 5.1», затем **Тест колонок** (Ctrl+T).

Плеер выводит PCM (без bitstream/passthrough): SPDIF занят картой, а DTS Connect сам кодирует поток.

## Сборка

`build.bat` (нужны Python 3.12/3.13 x64, 7-Zip, Inno Setup 6.3+): скачивает `libmpv-2.dll`, собирает `.exe` (PyInstaller) и установщик.
Запуск из исходников: `pip install -r requirements.txt`, `python tools/fetch_libmpv.py`, `python run.py`.
Тесты (Linux: libmpv, ffmpeg, Xvfb): `xvfb-run -a python -m pytest tests`.

---

## English

- **Formats:** MP3, FLAC (up to 24/192), ALAC, AAC, Opus, Vorbis, WAV, APE, WavPack, DSD (DSF/DFF) and more; multichannel FLAC/WAV/DSD, AC-3, DTS, DTS-HD MA, TrueHD.
- **CUE album images** split into tracks (UTF-8 / cp1251, embedded CUESHEET), seamless inside the image.
- **5.1** as multichannel PCM over WASAPI; channel mode (as in Windows / always 5.1 with 7.1 mixed down / stereo), centre and subwoofer levels, optional stereo → 5.1 upmix, a speaker test, and a format line like `FLAC 24/96 5.1 → PCM 6 ch`.
- Equalizer, ReplayGain, gapless playback, crossfade; cover art and tags; playlists with folders, drag & drop, repeat, shuffle, M3U/M3U8, resume on the next start.
- Live waveform for internet radio (what plays now, moving right to left); mini player (card or strip, translucent, with the waveform), 5.1 channel level meters (under the cover and a room view — V), global media keys, ⏮ ⏯ ⏭ in the taskbar preview, shortcuts (F1), Russian / English, **skins**: the ArtCore dark style and eight light ones — Light, Paper, Mint, Sakura, Sky, Lavender, Peach, Snow (menu ☰ → Skin, or Settings; applied at once).
- **Colours from the cover:** the waveform, the ▶ button, the playing row, the meters and a soft glow behind the cover take the album's colours (can be turned off in Settings).
- **Playlist groups:** an album gets a header with its cover, artist, year, format, track count and length; radio stations and loose tracks get groups of their own; a click on a header folds the group. Searching shows a plain list.
- Installer with "Open with", Default apps registration and a folder menu; self-update from GitHub Releases; a portable zip.

License: GNU GPL v3. Third-party components: [THIRD-PARTY.md](THIRD-PARTY.md).
