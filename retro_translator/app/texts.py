"""What the screens say, in each language the program translates into (the screens speak that language)."""

LANGUAGES = [("pt", "Português (Brasil)"), ("pt-PT", "Português (Portugal)"), ("es", "Español"), ("en", "English"),
             ("fr", "Français")]




TEXT = {  # the screens speak the language being translated into
    "pt": {"keys_ai": "← → ligar ou desligar", "ai": "Melhorar a tradução com IA", "ai_yes": "Sim (baixa 2,8 GB uma vez)", "ai_no": "Não", "why_ai": "Baixando a IA de tradução (só na primeira vez)", "ai_failed": "Sem a IA agora: tradução normal", "partial": "Só parte deste jogo pôde ser traduzida", "unreadable": "Não consegui ler as letras deste jogo.", "unreadable2": "Para não errar, ele não foi traduzido.", "another": "Enter: escolher outro jogo", "update": "NOVA VERSÃO {}: ATUALIZAR AGORA", "updating": "BAIXANDO A VERSÃO {}", "learn": "Aprendendo o jogo", "game": "Jogo", "folder": "Salvar o jogo traduzido em", "start": "TRADUZIR E JOGAR", "no_game": "Escolha um jogo (Enter)", "keys_home": "↑ ↓ mover   Enter escolher", "keys_lang": "← → trocar o idioma", "saved": "Salvo em", "screen_only": "Este jogo é traduzido na tela, enquanto você joga",
        "why_play": "Ele joga sozinho até chegar a menus e diálogos", "why_font": "Descobre qual desenho é cada letra", "why_kana": "Verifica se o jogo é escrito em japonês", "why_translate": "Cada texto encontrado vai para o seu idioma", "why_test": "Roda o jogo novo ao lado do original",
        "on": "TRADUÇÃO LIGADA", "off": "ORIGINAL (F1)", "working": "traduzindo...", "to": "Traduzir para:", "keys": "↑ ↓ escolher   Enter confirmar", "title": "PREPARANDO A TRADUÇÃO",
           "first": "Só na primeira vez deste jogo", "step": "ETAPA {} DE {}", "ready": "PRONTO!",
           "play": "Jogando para achar os textos", "font": "Aprendendo as letras do jogo",
           "kana": "Procurando letras japonesas", "translate": "Traduzindo os textos",
           "test": "Testando o jogo traduzido"},
    "pt-PT": {"keys_ai": "← → ligar ou desligar", "ai": "Melhorar a tradução com IA", "ai_yes": "Sim (transfere 2,8 GB uma vez)", "ai_no": "Não", "why_ai": "A transferir a IA de tradução (só da primeira vez)", "ai_failed": "Sem a IA agora: tradução normal", "partial": "Só parte deste jogo pôde ser traduzida", "unreadable": "Não consegui ler as letras deste jogo.", "unreadable2": "Para não errar, não foi traduzido.", "another": "Enter: escolher outro jogo", "update": "NOVA VERSÃO {}: ATUALIZAR AGORA", "updating": "A TRANSFERIR A VERSÃO {}", "learn": "A aprender o jogo", "game": "Jogo", "folder": "Guardar o jogo traduzido em", "start": "TRADUZIR E JOGAR", "no_game": "Escolha um jogo (Enter)", "keys_home": "↑ ↓ mover   Enter escolher", "keys_lang": "← → mudar a língua", "saved": "Guardado em", "screen_only": "Este jogo é traduzido no ecrã, enquanto joga",
        "why_play": "Joga sozinho até chegar a menus e diálogos", "why_font": "Descobre que desenho é cada letra", "why_kana": "Verifica se o jogo está escrito em japonês", "why_translate": "Cada texto encontrado passa para a sua língua", "why_test": "Corre o jogo novo ao lado do original",
        "on": "TRADUÇÃO LIGADA", "off": "ORIGINAL (F1)", "working": "a traduzir...", "to": "Traduzir para:", "keys": "↑ ↓ escolher   Enter confirmar", "title": "A PREPARAR A TRADUÇÃO",
              "first": "Só da primeira vez deste jogo", "step": "ETAPA {} DE {}", "ready": "PRONTO!",
              "play": "A jogar à procura dos textos", "font": "A aprender as letras do jogo",
              "kana": "A procurar letras japonesas", "translate": "A traduzir os textos",
              "test": "A testar o jogo traduzido"},
    "es": {"keys_ai": "← → activar o desactivar", "ai": "Mejorar la traducción con IA", "ai_yes": "Sí (descarga 2,8 GB una vez)", "ai_no": "No", "why_ai": "Descargando la IA de traducción (solo la primera vez)", "ai_failed": "Sin la IA ahora: traducción normal", "partial": "Solo parte de este juego se pudo traducir", "unreadable": "No pude leer las letras de este juego.", "unreadable2": "Para no equivocarme, no se tradujo.", "another": "Enter: elegir otro juego", "update": "NUEVA VERSIÓN {}: ACTUALIZAR YA", "updating": "DESCARGANDO LA VERSIÓN {}", "learn": "Aprendiendo el juego", "game": "Juego", "folder": "Guardar el juego traducido en", "start": "TRADUCIR Y JUGAR", "no_game": "Elige un juego (Enter)", "keys_home": "↑ ↓ mover   Enter elegir", "keys_lang": "← → cambiar el idioma", "saved": "Guardado en", "screen_only": "Este juego se traduce en pantalla mientras juegas",
        "why_play": "Juega solo hasta llegar a menús y diálogos", "why_font": "Descubre qué dibujo es cada letra", "why_kana": "Comprueba si el juego está en japonés", "why_translate": "Cada texto encontrado pasa a tu idioma", "why_test": "Ejecuta el juego nuevo junto al original",
        "on": "TRADUCCIÓN ACTIVADA", "off": "ORIGINAL (F1)", "working": "traduciendo...", "to": "Traducir al:", "keys": "↑ ↓ elegir   Enter confirmar", "title": "PREPARANDO LA TRADUCCIÓN",
           "first": "Solo la primera vez de este juego", "step": "PASO {} DE {}", "ready": "¡LISTO!",
           "play": "Jugando para hallar textos", "font": "Aprendiendo sus letras",
           "kana": "Buscando letras japonesas", "translate": "Traduciendo los textos",
           "test": "Probando el juego traducido"},
    "en": {"keys_ai": "← → turn on or off", "ai": "Improve the translation with AI", "ai_yes": "Yes (downloads 2.8 GB once)", "ai_no": "No", "why_ai": "Downloading the translation AI (only the first time)", "ai_failed": "No AI right now: normal translation", "partial": "Only part of this game could be translated", "unreadable": "I could not read this game's letters.", "unreadable2": "To avoid mistakes, it was not translated.", "another": "Enter: choose another game", "update": "NEW VERSION {}: UPDATE NOW", "updating": "DOWNLOADING VERSION {}", "learn": "Learning the game", "game": "Game", "folder": "Save the translated game in", "start": "TRANSLATE AND PLAY", "no_game": "Choose a game (Enter)", "keys_home": "↑ ↓ move   Enter choose", "keys_lang": "← → change the language", "saved": "Saved in", "screen_only": "This game is translated on screen while you play",
        "why_play": "It plays alone to reach menus and dialogs", "why_font": "It works out which drawing is which letter", "why_kana": "It checks whether the game is in Japanese", "why_translate": "Every text it found goes into your language", "why_test": "It runs the new game next to the original",
        "on": "TRANSLATION ON", "off": "ORIGINAL (F1)", "working": "translating...", "to": "Translate to:", "keys": "↑ ↓ choose   Enter confirm", "title": "PREPARING THE TRANSLATION",
           "first": "Only the first time for this game", "step": "STEP {} OF {}", "ready": "READY!",
           "play": "Playing to find the text", "font": "Learning the game's letters",
           "kana": "Looking for Japanese letters", "translate": "Translating the text",
           "test": "Testing the translated game"},
    "fr": {"keys_ai": "← → activer ou désactiver", "ai": "Améliorer la traduction avec l'IA", "ai_yes": "Oui (télécharge 2,8 Go une fois)", "ai_no": "Non", "why_ai": "Téléchargement de l'IA de traduction (la première fois)", "ai_failed": "Pas d'IA pour l'instant : traduction normale", "partial": "Seule une partie de ce jeu a pu être traduite", "unreadable": "Je n'ai pas pu lire les lettres du jeu.", "unreadable2": "Pour éviter les erreurs, il n'est pas traduit.", "another": "Entrée : choisir un autre jeu", "update": "NOUVELLE VERSION {} : METTRE À JOUR", "updating": "TÉLÉCHARGEMENT DE LA VERSION {}", "learn": "Apprend le jeu", "game": "Jeu", "folder": "Enregistrer le jeu traduit dans", "start": "TRADUIRE ET JOUER", "no_game": "Choisissez un jeu (Entrée)", "keys_home": "↑ ↓ déplacer   Entrée choisir", "keys_lang": "← → changer la langue", "saved": "Enregistré dans", "screen_only": "Ce jeu est traduit à l'écran pendant la partie",
        "why_play": "Il joue seul jusqu'aux menus et dialogues", "why_font": "Il trouve quel dessin est quelle lettre", "why_kana": "Il vérifie si le jeu est en japonais", "why_translate": "Chaque texte trouvé passe dans votre langue", "why_test": "Il lance le nouveau jeu à côté de l'original",
        "on": "TRADUCTION ACTIVE", "off": "ORIGINAL (F1)", "working": "traduction...", "to": "Traduire en :", "keys": "↑ ↓ choisir   Entrée valider", "title": "PRÉPARATION DE LA TRADUCTION",
           "first": "Seulement la première fois pour ce jeu", "step": "ÉTAPE {} SUR {}", "ready": "PRÊT !",
           "play": "Joue pour trouver les textes", "font": "Apprend les lettres du jeu",
           "kana": "Cherche le japonais", "translate": "Traduit les textes",
           "test": "Teste le jeu traduit"},
}
