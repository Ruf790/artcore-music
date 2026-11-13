"""Favourites (★) and the play history, in the data folder: favorites.json, history.json.

A track is known by its file and, for a CUE track, its place in the image (path + start) — so a star stays
on the track in every playlist and after a restart."""
from __future__ import annotations

import os
import time

from . import config
from .playlist import Track

HISTORY_MAX = 500


def key(tr: Track) -> str:
    p = tr.path if tr.is_stream else os.path.normcase(os.path.abspath(tr.path))
    return f"{p}|{tr.start:.2f}"


class Favorites:
    def __init__(self):
        raw = config._read("favorites.json")
        self.items: dict[str, dict] = {}
        for d in raw if isinstance(raw, list) else []:
            if isinstance(d, dict) and d.get("path"):
                tr = Track.from_dict(d)
                self.items[key(tr)] = tr.to_dict()

    def has(self, tr: Track) -> bool:
        return key(tr) in self.items

    def set(self, tr: Track, on: bool):
        k = key(tr)
        if on:
            d = tr.to_dict()
            d["added"] = int(time.time())
            self.items[k] = d
        else:
            self.items.pop(k, None)
        self.save()

    def toggle(self, tr: Track) -> bool:
        on = not self.has(tr)
        self.set(tr, on)
        return on

    def tracks(self) -> list[Track]:
        """Newest first."""
        ds = sorted(self.items.values(), key=lambda d: -int(d.get("added", 0)))
        return [Track.from_dict(d) for d in ds]

    def save(self):
        config._write("favorites.json", list(self.items.values()))


class History:
    def __init__(self):
        raw = config._read("history.json")
        self.items: list[dict] = [d for d in (raw if isinstance(raw, list) else []) if isinstance(d, dict)
                                  and d.get("path")]

    def add(self, tr: Track):
        k = key(tr)
        if self.items and self.items[0].get("_key") == k:      # the same track again (repeat): once
            self.items[0]["played"] = int(time.time())
        else:
            d = tr.to_dict()
            d["_key"] = k
            d["played"] = int(time.time())
            self.items.insert(0, d)
            del self.items[HISTORY_MAX:]
        self.save()

    def tracks(self, unique: bool = True) -> list[Track]:
        """Newest first; unique: every track once (its last play)."""
        seen: set[str] = set()
        out = []
        for d in self.items:
            k = d.get("_key", "")
            if unique and k in seen:
                continue
            seen.add(k)
            out.append(Track.from_dict(d))
        return out

    def clear(self):
        self.items = []
        self.save()

    def save(self):
        config._write("history.json", self.items)
