# Guitar Clone - PyGame Edition (v5)

Versao desktop do frontend React, feita em PyGame, usando o mesmo backend Flask
(`backend/guitar-clone-back.py`). O visual segue a linha do Guitar Hero/Guitar
Flash: pista em perspectiva, notas coloridas, holds, combo, multiplicador, score
e resultados.

## O que ja funciona

- Busca de musicas no Spotify pelo backend.
- Download do audio do YouTube + analise/chart automatica pelo backend.
- Upload de arquivo local (mp3, wav, ogg, flac, m4a).
- Faixa **DEMO** original gerada localmente, sem backend/internet (`F2`).
- Jogabilidade com 3/4/5 lanes conforme a dificuldade.
- Notas tap e hold (segurar), janelas de Perfect/Great/Good/Miss.
- Combo, multiplicador 1x/2x/3x/4x, score, precisao, max combo e grade S-F.
- Pausa, reinicio, tela de resultados, HUD, particulas e popups.
- Chart normalizada no cliente: notas bem espacadas, holds nunca atravessam
  outra nota do mesmo lane.
- Resultado com a nota em destaque (sem circulo), metricas centralizadas e
  aplausos/gritos de plateia ao fim da musica (sintetizados, sem estourar).
- Menu inicial limpo: pill ONLINE so com o ping verde e box da logo sem borda.
- Cache local de audios e capas carregadas em background.

## Como rodar

1. Instale as dependencias do cliente:

```bat
cd pygame-client
python -m pip install -r requirements.txt
```

2. Inicie o backend em outro terminal:

```bat
cd backend
set PYTHONIOENCODING=utf-8
.venv\Scripts\python guitar-clone-back.py
```

> No Windows o console usa cp1252 por padrao e o backend imprime emojis; sem
> `PYTHONIOENCODING=utf-8` ele pode encerrar com `UnicodeEncodeError`.

3. Rode o jogo:

```bat
cd pygame-client
python main.py
```

Atalho no Windows: `run.bat` (usa `python` do PATH).

### Demo sem backend

```bat
python main.py --demo
```

Ou clique em **DEMO** / pressione `F2` na tela de busca.

### Backend em outra porta/maquina

```bat
set GUITAR_BACKEND_URL=http://127.0.0.1:5000
python main.py
```

Ou:

```bat
python main.py --backend http://192.168.0.10:5000
```

## Controles

| Tela | Tecla | Acao |
| --- | --- | --- |
| Busca | digitar + `ENTER` | buscar no Spotify |
| Busca | `U` | escolher arquivo local |
| Busca | `F2` | iniciar demo |
| Busca | `1`-`4` | dificuldade |
| Busca | setas + `ENTER` | navegar e jogar |
| Jogo | `A S D J K` ou `1 2 3 4 5` | lanes (3/4/5 conforme dificuldade) |
| Jogo | `ESPACO` | comecar |
| Jogo | `ESC` / `P` | pausar/continuar |
| Pausa | `R` | reiniciar |
| Pausa | `M` | voltar a busca |
| Resultados | `R` / `ENTER` | jogar de novo |
| Resultados | `N` / `ESC` | nova musica |

`F11` alterna tela cheia. Arrastar um arquivo de audio sobre a janela tambem abre
o fluxo de upload.

## Estrutura

```
pygame-client/
  main.py          entrada / argumentos
  app.py           estados, threads, audio, integracao
  screens.py       busca, loading, resultados
  scene_game.py    pista, notas, HUD, pausa
  gameplay.py      regras: acertos, holds, combo, score
  chart.py         normalizacao da chart (gaps/holds)
  highway.py       geometria da perspectiva
  api.py           cliente HTTP do backend
  images.py        capas em background
  sound.py         SFX de interface e plateia do fim do show
  demo.py          faixa + chart demo locais
  ui.py            fontes, gradientes, glow, vinil
  config.py        constantes/cores
```

## Observacoes

- O backend precisa ter Spotify configurado para a busca. Sem Spotify, use a demo
  ou envie um arquivo local.
- Se o download do YouTube falhar com `HTTP 403: Forbidden`, o YouTube esta
  bloqueando o acesso anonimo (protecao anti-bot). Configure cookies para o
  yt-dlp antes de iniciar o backend:

```bat
set YT_COOKIES_BROWSER=chrome
rem ou: set YT_COOKIES_FILE=C:\caminho\cookies.txt
```

- Enquanto o YouTube estiver bloqueado, use o upload local (`U` na tela de busca)
  ou a demo (`F2`); o fluxo de analise e o mesmo.
- O primeiro download/analise pode demorar (yt-dlp + librosa). Depois o audio
  fica em `pygame-client/cache/`.
- Formatos como `.m4a`/`.flac` tentam conversao automatica via `ffmpeg` se ele
  estiver no PATH; caso contrario o jogo roda sem som e avisa na tela.
- A chart vem do backend, que combina beats/onsets com chroma. A sincronia e a
  mesma do frontend React; ajustes finos de offset podem ser feitos em
  `gameplay.py` (janelas) ou no backend.
- Se o jogo fechar inesperadamente, veja `pygame-client/crash.log`: o loop
  principal registra o traceback e, fora do modo headless, mostra uma tela de
  erro com o caminho do log.
