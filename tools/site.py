"""Development: builds the public website (GitHub Pages of the downloads repository), one static page per language
(English at the root, the others in /pt/, /es/, /fr/, /ja/) with hreflang links, structured data and a sitemap.
The screenshots are real captures of the program (tools/cjk_screen.py). Usage: python -m tools.site OUT_DIR"""
import html
import json
import os
import sys

BASE = "https://leofeitosa.github.io/retro-translator/"
DOWNLOAD = "https://github.com/LeoFeitosa/retro-translator/releases/latest/download/retro-translator.exe"
REPO = "https://github.com/LeoFeitosa/retro-translator"
SHOTS = ["pt", "pt-PT", "es", "en", "fr"]  # translations the screenshots show: every language games are translated into
NAMES = {"en": "English", "pt": "Português (Brasil)", "pt-PT": "Português (Portugal)", "es": "Español",
         "fr": "Français", "ja": "日本語"}
HREFLANG = {"pt": "pt-BR"}  # page key -> hreflang and html lang
LABEL = {"pt": "PT-BR", "pt-PT": "PT-PT"}
CURRENT = ' aria-current="page"'
VIDEO_DATE = "2026-11-26"  # promotional videos (tools/promo.py): assets/video/retro-translator-<page>.mp4
LOCALE = {"en": "en_US", "pt": "pt_BR", "pt-PT": "pt_PT", "es": "es_ES", "fr": "fr_FR", "ja": "ja_JP"}

TEXT = {
    "en": {
        "video_h": 'See it working', "video_d": 'Real footage: the program picks the language, learns the game and translates it while it is played.',
        "title": "Retro Translator: play retro games translated into your language",
        "desc": "Free Windows program that translates Mega Drive / Genesis games while you play. Japanese, English, "
                "French and Spanish games into English, Portuguese, Spanish or French. Offline and portable.",
        "h1": "Play retro games in your own language",
        "lead": "Pick a game, pick a language, and play. Retro Translator learns how each game writes its text and "
                "translates it on the game's own screens.",
        "download": "Download for Windows",
        "facts": "Free for Windows 10 and 11. One file, nothing to install, works offline. Games not included.",
        "tv": "A real screen from a Japanese game, translated by the program.",
        "lang": "Translation", "orig": "Original", "trans": "Translated",
        "how_h": "What happens when you open a game",
        "how": ["The first time, the program plays the game by itself for a few minutes. It works out which "
                "drawing is which letter, the way you would crack a code, and finds where the text lives.",
                "Text stored in the game is rewritten in your language, so menus and dialog keep the game's own "
                "lettering and colours. Text it cannot rewrite is drawn over the screen instead.",
                "Japanese is read straight from the screen, kana and kanji, and translated by a model that runs "
                "on your computer. Nothing is sent anywhere."],
        "steps_h": "Three steps",
        "steps": [("Download", "Get retro-translator.exe from this page. It is a single file."),
                  ("Open a game", "Choose a ROM and the language you want to play in."),
                  ("Play", "The game starts translated. F1 switches back to the original text.")],
        "langs_h": "Languages and consoles",
        "games_in": "Games in", "play_in": "Play in",
        "console": "Console", "status": "Status", "md": "Mega Drive / Genesis", "yes": "Supported",
        "more": "Other consoles", "soon": "Planned",
        "faq_h": "Questions",
        "faq": [("Is it free?", "Yes. It cannot be sold: the emulator it uses does not allow commercial use."),
                ("Do I need to install anything?", "No. Download one file and open it. A new version cleans up "
                 "after the old one by itself."),
                ("Where do I get games?", "Games are not included. Use copies of games you own."),
                ("Is the translation perfect?", "Most text reads well; some comes out literal or wrong, and text "
                 "drawn as pictures, like logos, stays as it is."),
                ("Does it need the internet?", "No. Everything runs on your own computer, on the CPU.")],
        "alt_save": "Japanese Mega Drive game asking where to save, translated into {lang}",
        "alt_talk": "Dialog of a Japanese Mega Drive game translated into {lang}",
        "foot": "Retro Translator is free software for playing retro games.", "licenses": "Licenses",
    },
    "pt": {
        "video_h": 'Veja funcionando', "video_d": 'Imagens reais: o programa escolhe o idioma, aprende o jogo e traduz enquanto se joga.',
        "title": "Retro Translator: jogue games retrô traduzidos para o português",
        "desc": "Programa gratuito para Windows que traduz jogos de Mega Drive enquanto você joga. Jogos em "
                "japonês, inglês, francês e espanhol em português do Brasil ou de Portugal. Offline e portátil.",
        "h1": "Jogue games retrô no seu idioma",
        "lead": "Escolha o jogo, escolha o idioma e jogue. O Retro Translator aprende como cada jogo escreve o "
                "texto e traduz nas próprias telas do jogo.",
        "download": "Baixar para Windows",
        "facts": "Grátis para Windows 10 e 11. Um arquivo só, sem instalar nada, funciona sem internet. "
                 "Jogos não incluídos.",
        "tv": "Uma tela real de um jogo japonês, traduzida pelo programa.",
        "lang": "Tradução", "orig": "Original", "trans": "Traduzido",
        "how_h": "O que acontece quando você abre um jogo",
        "how": ["Na primeira vez, o programa joga sozinho por alguns minutos. Ele descobre qual desenho é qual "
                "letra, como quem decifra um código, e encontra onde o texto fica guardado.",
                "O texto guardado no jogo é reescrito no seu idioma, e menus e diálogos mantêm as letras e as "
                "cores do próprio jogo. O que não dá para reescrever é desenhado por cima da tela.",
                "O japonês é lido direto da tela, kana e kanji, e traduzido por um modelo que roda no seu "
                "computador. Nada é enviado para lugar nenhum."],
        "steps_h": "Três passos",
        "steps": [("Baixe", "Pegue o retro-translator.exe nesta página. É um arquivo só."),
                  ("Abra um jogo", "Escolha a ROM e o idioma em que quer jogar."),
                  ("Jogue", "O jogo começa traduzido. F1 volta para o texto original.")],
        "langs_h": "Idiomas e consoles",
        "games_in": "Jogos em", "play_in": "Jogue em",
        "console": "Console", "status": "Situação", "md": "Mega Drive / Genesis", "yes": "Funciona",
        "more": "Outros consoles", "soon": "Planejado",
        "faq_h": "Perguntas",
        "faq": [("É grátis?", "Sim. Não pode ser vendido: o emulador que ele usa não permite uso comercial."),
                ("Preciso instalar alguma coisa?", "Não. Baixe um arquivo e abra. Uma versão nova limpa sozinha o "
                 "que a antiga deixou."),
                ("Onde consigo os jogos?", "Os jogos não vêm junto. Use cópias de jogos que você tem."),
                ("A tradução é perfeita?", "A maior parte fica boa; uma parte sai literal ou errada, e texto "
                 "desenhado como imagem, como logotipos, continua como está."),
                ("Precisa de internet?", "Não. Tudo roda no seu computador, no processador.")],
        "alt_save": "Jogo japonês de Mega Drive perguntando onde salvar, traduzido para {lang}",
        "alt_talk": "Diálogo de um jogo japonês de Mega Drive traduzido para {lang}",
        "foot": "Retro Translator é um programa gratuito para jogar games retrô.", "licenses": "Licenças",
    },
    "pt-PT": {
        "video_h": 'Veja a funcionar', "video_d": 'Imagens reais: o programa escolhe a língua, aprende o jogo e traduz enquanto se joga.',
        "title": "Retro Translator: jogue jogos retro traduzidos para português de Portugal",
        "desc": "Programa gratuito para Windows que traduz jogos de Mega Drive enquanto joga. Jogos em japonês, "
                "inglês, francês e espanhol em português de Portugal. Funciona sem internet e não precisa de instalação.",
        "h1": "Jogue jogos retro na sua língua",
        "lead": "Escolha o jogo, escolha a língua e jogue. O Retro Translator aprende como cada jogo escreve o texto "
                "e traduz nos próprios ecrãs do jogo.",
        "download": "Transferir para Windows",
        "facts": "Gratuito para Windows 10 e 11. Um único ficheiro, sem instalar nada, funciona sem internet. "
                 "Jogos não incluídos.",
        "tv": "Um ecrã real de um jogo japonês, traduzido pelo programa.",
        "lang": "Tradução", "orig": "Original", "trans": "Traduzido",
        "how_h": "O que acontece quando abre um jogo",
        "how": ["Da primeira vez, o programa joga sozinho durante alguns minutos. Descobre que desenho corresponde a "
                "que letra, como quem decifra um código, e encontra onde o texto está guardado.",
                "O texto guardado no jogo é reescrito na sua língua, e os menus e diálogos mantêm as letras e as "
                "cores do próprio jogo. O que não é possível reescrever é desenhado por cima do ecrã.",
                "O japonês é lido diretamente do ecrã, kana e kanji, e traduzido por um modelo que corre no seu "
                "computador. Nada é enviado para lado nenhum."],
        "steps_h": "Três passos",
        "steps": [("Transfira", "Obtenha o retro-translator.exe nesta página. É um único ficheiro."),
                  ("Abra um jogo", "Escolha a ROM e a língua em que quer jogar."),
                  ("Jogue", "O jogo começa traduzido. F1 volta ao texto original.")],
        "langs_h": "Línguas e consolas",
        "games_in": "Jogos em", "play_in": "Jogue em",
        "console": "Consola", "status": "Estado", "md": "Mega Drive / Genesis", "yes": "Suportada",
        "more": "Outras consolas", "soon": "Prevista",
        "faq_h": "Perguntas",
        "faq": [("É gratuito?", "Sim. Não pode ser vendido: o emulador que utiliza não permite uso comercial."),
                ("Tenho de instalar alguma coisa?", "Não. Transfira um ficheiro e abra-o. Uma versão nova limpa "
                 "sozinha o que a anterior deixou."),
                ("Onde arranjo os jogos?", "Os jogos não estão incluídos. Use cópias de jogos que tenha."),
                ("A tradução é perfeita?", "A maior parte lê-se bem; uma parte sai literal ou errada, e o texto "
                 "desenhado como imagem, como os logótipos, fica como está."),
                ("Precisa de internet?", "Não. Tudo corre no seu computador, no processador.")],
        "alt_save": "Jogo japonês de Mega Drive a perguntar onde guardar, traduzido para {lang}",
        "alt_talk": "Diálogo de um jogo japonês de Mega Drive traduzido para {lang}",
        "foot": "O Retro Translator é um programa gratuito para jogar jogos retro.", "licenses": "Licenças",
    },
    "es": {
        "video_h": 'Míralo en acción', "video_d": 'Imágenes reales: el programa elige el idioma, aprende el juego y lo traduce mientras se juega.',
        "title": "Retro Translator: juega juegos retro traducidos al español",
        "desc": "Programa gratuito para Windows que traduce juegos de Mega Drive mientras juegas. Juegos en "
                "japonés, inglés y francés al español, inglés, portugués o francés. Sin conexión y portátil.",
        "h1": "Juega juegos retro en tu idioma",
        "lead": "Elige el juego, elige el idioma y juega. Retro Translator aprende cómo escribe cada juego su texto "
                "y lo traduce en las propias pantallas del juego.",
        "download": "Descargar para Windows",
        "facts": "Gratis para Windows 10 y 11. Un solo archivo, sin instalar nada, funciona sin conexión. "
                 "Juegos no incluidos.",
        "tv": "Una pantalla real de un juego japonés, traducida por el programa.",
        "lang": "Traducción", "orig": "Original", "trans": "Traducido",
        "how_h": "Qué pasa cuando abres un juego",
        "how": ["La primera vez, el programa juega solo durante unos minutos. Descubre qué dibujo es cada letra, "
                "como quien descifra un código, y encuentra dónde está guardado el texto.",
                "El texto guardado en el juego se reescribe en tu idioma, y los menús y diálogos conservan las "
                "letras y los colores del juego. Lo que no se puede reescribir se dibuja sobre la pantalla.",
                "El japonés se lee directamente de la pantalla, kana y kanji, y lo traduce un modelo que funciona "
                "en tu ordenador. No se envía nada a ningún sitio."],
        "steps_h": "Tres pasos",
        "steps": [("Descarga", "Consigue retro-translator.exe en esta página. Es un solo archivo."),
                  ("Abre un juego", "Elige la ROM y el idioma en que quieres jugar."),
                  ("Juega", "El juego empieza traducido. F1 vuelve al texto original.")],
        "langs_h": "Idiomas y consolas",
        "games_in": "Juegos en", "play_in": "Juega en",
        "console": "Consola", "status": "Estado", "md": "Mega Drive / Genesis", "yes": "Funciona",
        "more": "Otras consolas", "soon": "Previsto",
        "faq_h": "Preguntas",
        "faq": [("¿Es gratis?", "Sí. No se puede vender: el emulador que usa no permite el uso comercial."),
                ("¿Tengo que instalar algo?", "No. Descarga un archivo y ábrelo. Una versión nueva limpia sola lo "
                 "que dejó la anterior."),
                ("¿Dónde consigo los juegos?", "Los juegos no vienen incluidos. Usa copias de juegos que tengas."),
                ("¿La traducción es perfecta?", "La mayor parte se lee bien; una parte sale literal o mal, y el "
                 "texto dibujado como imagen, como los logotipos, se queda como está."),
                ("¿Necesita internet?", "No. Todo funciona en tu ordenador, en el procesador.")],
        "alt_save": "Juego japonés de Mega Drive preguntando dónde guardar, traducido al {lang}",
        "alt_talk": "Diálogo de un juego japonés de Mega Drive traducido al {lang}",
        "foot": "Retro Translator es un programa gratuito para jugar juegos retro.", "licenses": "Licencias",
    },
    "fr": {
        "video_h": 'Voyez-le en action', "video_d": 'Images réelles : le logiciel choisit la langue, apprend le jeu et le traduit pendant la partie.',
        "title": "Retro Translator : jouez aux jeux rétro traduits en français",
        "desc": "Logiciel gratuit pour Windows qui traduit les jeux Mega Drive pendant que vous jouez. Jeux en "
                "japonais, anglais et espagnol en français, anglais, espagnol ou portugais. Hors ligne et portable.",
        "h1": "Jouez aux jeux rétro dans votre langue",
        "lead": "Choisissez le jeu, choisissez la langue, et jouez. Retro Translator apprend comment chaque jeu "
                "écrit son texte et le traduit sur les écrans du jeu lui-même.",
        "download": "Télécharger pour Windows",
        "facts": "Gratuit pour Windows 10 et 11. Un seul fichier, rien à installer, fonctionne hors ligne. "
                 "Jeux non fournis.",
        "tv": "Un vrai écran d'un jeu japonais, traduit par le logiciel.",
        "lang": "Traduction", "orig": "Original", "trans": "Traduit",
        "how_h": "Ce qui se passe quand vous ouvrez un jeu",
        "how": ["La première fois, le logiciel joue seul pendant quelques minutes. Il trouve quel dessin "
                "correspond à quelle lettre, comme on déchiffre un code, et repère où le texte est rangé.",
                "Le texte rangé dans le jeu est réécrit dans votre langue : menus et dialogues gardent les lettres "
                "et les couleurs du jeu. Ce qui ne peut pas être réécrit est dessiné par-dessus l'écran.",
                "Le japonais est lu directement à l'écran, kana et kanji, et traduit par un modèle qui tourne sur "
                "votre ordinateur. Rien n'est envoyé nulle part."],
        "steps_h": "Trois étapes",
        "steps": [("Téléchargez", "Récupérez retro-translator.exe sur cette page. C'est un seul fichier."),
                  ("Ouvrez un jeu", "Choisissez la ROM et la langue dans laquelle vous voulez jouer."),
                  ("Jouez", "Le jeu démarre traduit. F1 revient au texte d'origine.")],
        "langs_h": "Langues et consoles",
        "games_in": "Jeux en", "play_in": "Jouez en",
        "console": "Console", "status": "État", "md": "Mega Drive / Genesis", "yes": "Pris en charge",
        "more": "Autres consoles", "soon": "Prévu",
        "faq_h": "Questions",
        "faq": [("Est-ce gratuit ?", "Oui. Il ne peut pas être vendu : l'émulateur utilisé interdit l'usage "
                 "commercial."),
                ("Faut-il installer quelque chose ?", "Non. Téléchargez un fichier et ouvrez-le. Une nouvelle "
                 "version nettoie seule ce que l'ancienne a laissé."),
                ("Où trouver les jeux ?", "Les jeux ne sont pas fournis. Utilisez des copies de jeux que vous "
                 "possédez."),
                ("La traduction est-elle parfaite ?", "La plupart du texte se lit bien ; une partie sort littérale "
                 "ou fausse, et le texte dessiné comme une image, comme les logos, reste tel quel."),
                ("Faut-il internet ?", "Non. Tout tourne sur votre ordinateur, sur le processeur.")],
        "alt_save": "Jeu japonais Mega Drive demandant où sauvegarder, traduit en {lang}",
        "alt_talk": "Dialogue d'un jeu japonais Mega Drive traduit en {lang}",
        "foot": "Retro Translator est un logiciel gratuit pour jouer aux jeux rétro.", "licenses": "Licences",
    },
    "ja": {
        "video_h": '実際の動き', "video_d": '実際の映像：言語を選び、ゲームを覚え、遊びながら翻訳します。',
        "title": "Retro Translator：レトロゲームをあなたの言語で遊ぶ",
        "desc": "メガドライブのゲームをプレイしながら翻訳する、Windows 用の無料ソフト。日本語のゲームを英語・"
                "ポルトガル語・スペイン語・フランス語に。オフラインで動き、インストール不要。",
        "h1": "レトロゲームを、好きな言語で",
        "lead": "ゲームを選び、言語を選んで、遊ぶだけ。Retro Translator はゲームごとの文字の書き方を覚え、"
                "ゲーム自身の画面の上で翻訳します。",
        "download": "Windows 版をダウンロード",
        "facts": "Windows 10・11 対応の無料ソフト。ファイルひとつで、インストール不要、オフラインで動きます。"
                 "ゲームは含まれていません。",
        "tv": "日本語のゲームの実際の画面を、このソフトで翻訳したものです。",
        "lang": "翻訳", "orig": "原文", "trans": "翻訳後",
        "how_h": "ゲームを開くと起きること",
        "how": ["初回は、ソフトが数分間ひとりでゲームを遊びます。暗号を解くように、どの絵がどの文字かを"
                "割り出し、テキストがどこに入っているかを見つけます。",
                "ゲームに入っているテキストは選んだ言語に書き換えられ、メニューや会話はゲーム本来の文字と色の"
                "まま表示されます。書き換えられないテキストは画面の上に描きます。",
                "日本語はかなも漢字も画面から直接読み取り、あなたのパソコンの中で動くモデルが翻訳します。"
                "外部には何も送りません。"],
        "steps_h": "3 つのステップ",
        "steps": [("ダウンロード", "このページから retro-translator.exe を入手します。ファイルはひとつだけです。"),
                  ("ゲームを開く", "ROM と、遊びたい言語を選びます。"),
                  ("遊ぶ", "ゲームは翻訳された状態で始まります。F1 で原文に戻せます。")],
        "langs_h": "言語とゲーム機",
        "games_in": "ゲームの言語", "play_in": "翻訳先",
        "console": "ゲーム機", "status": "状況", "md": "メガドライブ / Genesis", "yes": "対応",
        "more": "ほかのゲーム機", "soon": "予定",
        "faq_h": "よくある質問",
        "faq": [("無料ですか？", "はい。販売はできません。使用しているエミュレーターが商用利用を認めていないためです。"),
                ("インストールは必要ですか？", "いいえ。ファイルをひとつダウンロードして開くだけです。新しい版は古い版の"
                 "データを自動で片づけます。"),
                ("ゲームはどこで手に入れますか？", "ゲームは含まれていません。お持ちのゲームのコピーを使ってください。"),
                ("翻訳は完璧ですか？", "ほとんどは自然に読めますが、直訳や誤訳もあります。ロゴのように絵で描かれた"
                 "文字はそのままです。"),
                ("インターネットは必要ですか？", "いいえ。すべてあなたのパソコンの CPU で動きます。")],
        "alt_save": "セーブ先をたずねる日本語のメガドライブのゲーム（{lang}に翻訳）",
        "alt_talk": "日本語のメガドライブのゲームの会話（{lang}に翻訳）",
        "foot": "Retro Translator はレトロゲームを遊ぶための無料ソフトです。", "licenses": "ライセンス",
    },
}
GAME_LANGS = {"en": ["Japanese", "English", "French", "Spanish"], "pt": ["Japonês", "Inglês", "Francês", "Espanhol"],
              "pt-PT": ["Japonês", "Inglês", "Francês", "Espanhol"],
              "es": ["Japonés", "Inglés", "Francés", "Español"], "fr": ["Japonais", "Anglais", "Français", "Espagnol"],
              "ja": ["日本語", "英語", "フランス語", "スペイン語"]}
PLAY_LANGS = {"en": ["Portuguese (Brazil)", "Portuguese (Portugal)", "Spanish", "English", "French"],
              "pt": ["Português do Brasil", "Português de Portugal", "Espanhol", "Inglês", "Francês"],
              "pt-PT": ["Português do Brasil", "Português de Portugal", "Espanhol", "Inglês", "Francês"],
              "es": ["Portugués de Brasil", "Portugués de Portugal", "Español", "Inglés", "Francés"],
              "fr": ["Portugais du Brésil", "Portugais du Portugal", "Espagnol", "Anglais", "Français"],
              "ja": ["ポルトガル語（ブラジル）", "ポルトガル語（ポルトガル）", "スペイン語", "英語", "フランス語"]}
SHOT_NAMES = {k: dict(zip(SHOTS, v)) for k, v in PLAY_LANGS.items()}  # PLAY_LANGS follows the SHOTS order


def folder(lang):
    return "" if lang == "en" else lang.lower() + "/"


def url(lang):
    return BASE + folder(lang)


def page(lang):
    t, e, root = TEXT[lang], html.escape, "" if lang == "en" else "../"
    shown = lang if lang in SHOTS else "en"
    alternates = "\n".join(f'<link rel="alternate" hreflang="{HREFLANG.get(l, l)}" href="{url(l)}">' for l in TEXT) + \
        f'\n<link rel="alternate" hreflang="x-default" href="{BASE}">'
    data = [{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Retro Translator",
             "operatingSystem": "Windows 10, Windows 11", "applicationCategory": "GameApplication",
             "description": t["desc"], "inLanguage": HREFLANG.get(lang, lang), "url": url(lang), "downloadUrl": DOWNLOAD,
             "image": BASE + "assets/share.png", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
            {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": HREFLANG.get(lang, lang),
             "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                            for q, a in t["faq"]]},
            {"@context": "https://schema.org", "@type": "VideoObject", "name": f"Retro Translator: {t['video_h']}",
             "description": t["video_d"], "inLanguage": HREFLANG.get(lang, lang), "uploadDate": VIDEO_DATE,
             "thumbnailUrl": f"{BASE}assets/video/poster-{lang}.jpg",
             "contentUrl": f"{BASE}assets/video/retro-translator-{lang}.mp4"}]
    langs = "".join(f'<a href="{root}{folder(l)}" hreflang="{HREFLANG.get(l, l)}" lang="{HREFLANG.get(l, l)}"'
                    f'{CURRENT if l == lang else ""}>{NAMES[l]}</a>' for l in TEXT)
    buttons = "".join(f'<button type="button" data-shot="{l}" aria-pressed="{str(l == shown).lower()}">'
                      f'{LABEL.get(l, l.upper())}</button>' for l in SHOTS)
    alt = lambda k, l: e(t[k].format(lang=SHOT_NAMES[lang][l]))
    steps = "".join(f"<li><h3>{e(a)}</h3><p>{e(b)}</p></li>" for a, b in t["steps"])
    faq = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in t["faq"])
    how = "".join(f"<p>{e(p)}</p>" for p in t["how"])
    li = lambda xs: "".join(f"<li>{e(x)}</li>" for x in xs)
    redirect = """<script>(function(){try{if(localStorage.getItem("rt-lang"))return}catch(e){}
var l=navigator.languages||[navigator.language||""];
for(var i=0;i<l.length;i++){var x=l[i].toLowerCase(),b=x.slice(0,2);if(b==="en")return;
if(x==="pt-pt"){location.replace("pt-pt/");return}if(["pt","es","fr","ja"].indexOf(b)>=0){
location.replace(b+"/");return}}})()</script>""" if lang == "en" else ""
    return f"""<!doctype html>
<html lang="{HREFLANG.get(lang, lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t["title"])}</title>
<meta name="description" content="{e(t["desc"])}">
<link rel="canonical" href="{url(lang)}">
{alternates}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Retro Translator">
<meta property="og:locale" content="{LOCALE[lang]}">
<meta property="og:title" content="{e(t["title"])}">
<meta property="og:description" content="{e(t["desc"])}">
<meta property="og:url" content="{url(lang)}">
<meta property="og:image" content="{BASE}assets/share.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="840">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#16193b">
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;700&family=Karla:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/site.css">
<link rel="preload" as="image" href="{root}assets/save-{shown}.png">
<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>
{redirect}
</head>
<body>
<header class="top">
<a class="mark" href="{root or './'}"><img src="{root}assets/icon.svg" alt="" width="22" height="22">Retro Translator</a>
<nav class="langs" aria-label="Language">{langs}</nav>
</header>
<main>
<section class="hero">
<div class="pitch">
<h1>{e(t["h1"])}</h1>
<p class="lead">{e(t["lead"])}</p>
<a class="get" href="{DOWNLOAD}">{e(t["download"])}</a>
<p class="facts">{e(t["facts"])}</p>
</div>
<figure class="tv" data-root="{root}">
<div class="screen"><img id="shot" src="{root}assets/save-{shown}.png" width="320" height="224" alt="{alt("alt_save", shown)}"></div>
<div class="panel">
<div class="group" role="group" aria-label="{e(t["lang"])}">{buttons}</div>
<div class="group" role="group"><button type="button" data-view="orig" aria-pressed="false">{e(t["orig"])}</button><button type="button" data-view="trans" aria-pressed="true">{e(t["trans"])}</button></div>
</div>
<figcaption>{e(t["tv"])}</figcaption>
</figure>
</section>
<section class="video"><h2>{e(t["video_h"])}</h2><p>{e(t["video_d"])}</p>
<video controls preload="none" playsinline width="1920" height="1080" poster="{root}assets/video/poster-{lang}.jpg">
<source src="{root}assets/video/retro-translator-{lang}.mp4" type="video/mp4"></video></section>
<section class="how">
<div class="text"><h2>{e(t["how_h"])}</h2>{how}</div>
<div class="pair">
<img src="{root}assets/talk-ja.png" width="320" height="224" loading="lazy" alt="{e(t["orig"])}">
<img src="{root}assets/talk-{shown}.png" width="320" height="224" loading="lazy" alt="{alt("alt_talk", shown)}">
</div>
</section>
<section class="steps"><h2>{e(t["steps_h"])}</h2><ol>{steps}</ol></section>
<section class="support">
<h2>{e(t["langs_h"])}</h2>
<div class="cols">
<div><h3>{e(t["games_in"])}</h3><ul>{li(GAME_LANGS[lang])}</ul></div>
<div><h3>{e(t["play_in"])}</h3><ul>{li(PLAY_LANGS[lang])}</ul></div>
<table><thead><tr><th>{e(t["console"])}</th><th>{e(t["status"])}</th></tr></thead>
<tbody><tr><td>{e(t["md"])}</td><td class="on">{e(t["yes"])}</td></tr><tr><td>{e(t["more"])}</td><td>{e(t["soon"])}</td></tr></tbody></table>
</div>
</section>
<section class="faq"><h2>{e(t["faq_h"])}</h2>{faq}</section>
</main>
<footer><p>{e(t["foot"])}</p><p><a href="{REPO}">GitHub</a> <a href="{REPO}/blob/main/THIRD_PARTY.md">{e(t["licenses"])}</a></p></footer>
<script src="{root}assets/site.js" defer></script>
</body>
</html>
"""


def main(out):
    for lang in TEXT:
        d = os.path.join(out, folder(lang))
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(page(lang))
    links = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{HREFLANG.get(l, l)}" href="{url(l)}"/>' for l in TEXT)
    urls = "".join(f"\n  <url><loc>{url(l)}</loc>{links}\n    <xhtml:link rel=\"alternate\" hreflang=\"x-default\" "
                   f"href=\"{BASE}\"/>\n  </url>" for l in TEXT)
    open(os.path.join(out, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        f'xmlns:xhtml="http://www.w3.org/1999/xhtml">{urls}\n</urlset>\n')
    open(os.path.join(out, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n")


if __name__ == "__main__":
    main(sys.argv[1])
