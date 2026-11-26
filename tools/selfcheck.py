"""Development: quick checks of the shared code that need no ROM; each prints what it read or fails an assert.
Usage: python -m tools.selfcheck"""
from retro_translator.core.reading.kana_kanji import convert
from retro_translator.core.rewriting.rom_text import real_words
from retro_translator.core.translating import neural
from retro_translator.core.translating.translation import translate, translate_batch


def words():
    """A message read with a missing or wrong letter is not written into the ROM."""
    for text in ["OU HAVE A LONG ROAD", "T'S NOT A GOOD IDEA", "SEORET PASSAGE", "OTHING HAPPENS.", "LL MEMORIES"]:
        assert not real_words(text), text
    for text in ["You have a long road.", "CAN'T CARRY ANY", "WE'LL SEE", "SNOOKER GAMES", "OPTIONS", "START RACE"]:
        assert real_words(text), text


def kana():
    for t, expected in [("せんとうそくど", "戦闘速度"), ("ひとりごと", "独り言"), ("ボタンせってい", "ボタン設定")]:
        print(t, "->", convert(t), "(", expected, ")")
    for t in ["ぼくもすこしのんじゃおっと。ゴクゴクゴク…", "どこにセーブする？", "レスタをつかった！しかしこうかがなかった。"]:
        print(t, "->", convert(t))


def neural_model():
    print(neural.translate(["せんとうそくど", "どこにセーブする？", "レスタをつかった！しかしこうかがなかった。"], "ja"))
    print(neural.translate(["开始游戏", "你要保存吗？"], "zh"))


def rules():
    assert translate("GAME OVER") == "FIM DE JOGO"
    assert translate("Press Start") == "Aperte start"
    fs = ["YOU FOUND THE RED KEY!", "Do you want to save your game?", "The castle is guarded by an evil wizard.",
          "Thank you! But our princess is in another castle.", "Your energy is low. Find food quickly."]
    for f, t in zip(fs, translate_batch(fs)):
        print(f, "->", t)


if __name__ == "__main__":
    words()
    rules()
    kana()
    neural_model()
    print("ok")
