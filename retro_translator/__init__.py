"""Retro Translator: plays retro console games translated into the player's language, offline."""
import os

VERSION = "0.3.5"  # raise before every release: older builds offer the update when the published one is newer
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")  # versioned data (glossary, rules, kanji) and built data (tables, neural model)
