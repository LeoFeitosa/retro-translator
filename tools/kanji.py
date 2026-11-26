"""Development: builds the kana -> kanji converter data (retro_translator/data/kanji/) from the Mozc open-source dictionary (IPAdic-based;
licenses in THIRD_PARTY.md). Words above COST_MAX (rare) are left out to keep the package small.
Usage: python -m tools.kanji MOZC_DICTIONARY_OSS_DIR"""
import gzip
import os
import sys

import numpy as np

from retro_translator import DATA

COST_MAX = 7000


def main(folder):
    os.makedirs(os.path.join(DATA, "kanji"), exist_ok=True)
    n = 0
    with gzip.open(os.path.join(DATA, "kanji", "dic.tsv.gz"), "wt", encoding="utf-8") as out_:
        for i in range(10):
            for line in open(os.path.join(folder, f"dictionary{i:02d}.txt"), encoding="utf-8"):
                reading, lid, rid, cost, word = line.rstrip("\n").split("\t")[:5]
                if int(cost) <= COST_MAX and len(reading) <= 12:
                    out_.write("\t".join((reading, lid, rid, cost, word)) + "\n")
                    n += 1
    values_ = open(os.path.join(folder, "connection_single_column.txt")).read().split()
    side = int(values_[0])
    np.savez_compressed(os.path.join(DATA, "kanji", "connection.npz"), c=np.array(values_[1:], np.int16).reshape(side, side))
    print(n, "words,", side, "ids")


if __name__ == "__main__":
    main(sys.argv[1])
