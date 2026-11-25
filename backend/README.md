# Backend Flask — Guitar Clone

Documentação específica do backend: o que cada parte faz, quais endpoints
existem, como o áudio é baixado/armazenado e como a chart é gerada.

O backend inteiro está em um único arquivo: `backend/guitar-clone-back.py`.

---

## 1. Visão geral

O backend é uma API Flask com CORS liberado, feita para rodar em
`http://127.0.0.1:5000`. Ele tem quatro responsabilidades:

1. **Buscar músicas no Spotify** (metadados: nome, artista, capa, duração).
2. **Baixar o áudio do YouTube** com `yt-dlp`, convertendo para MP3 192 kbps.
3. **Analisar o áudio** com `librosa` e gerar a chart (notas) do jogo.
4. **Servir o MP3** para o cliente PyGame tocar em streaming.

Fluxo de uma partida:

```
cliente PyGame
   │  GET /search/spotify?q=...
   │  POST /analyze/youtube {query, difficulty}
   ▼
backend
   ├─ cache_id = md5(query)
   ├─ baixa do YouTube (ou reaproveita .mp3 do cache)
   ├─ librosa: beats, onsets, chroma, spectral centroid
   ├─ generate_notes_with_duration(...)  → notes[]
   └─ responde {audio_info, notes, cache_id, audio_url}
   │
   │  GET /stream/<cache_id>
   ▼
cliente recebe o MP3 e joga a chart
```

O cliente roda a requisição de análise em uma thread própria
(`pygame-client/tasks.py`), porque a análise leva dezenas de segundos.

---

## 2. Como rodar

```powershell
cd C:\Projetos-Pessoais\Guitar-Clone\backend
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe guitar-clone-back.py
```

```bash
# WSL / Linux
cd ~/Guitar-Clone/backend
export PYTHONIOENCODING=utf-8
.venv/bin/python guitar-clone-back.py
```

Dependências: `backend/requirements.txt` (`flask`, `flask-cors`, `librosa`,
`numpy`, `scipy`, `soundfile`, `spotipy`, `yt-dlp`, `python-dotenv`).

Também são necessários no sistema:

- **ffmpeg** no `PATH` — o `yt-dlp` usa para extrair/converter o MP3.
- **Node.js 20+** ou **Deno** — runtime JS exigido pelo YouTube em 2026.

A instalação completa está no `README.md` da raiz (seções 2 e 3).

O servidor sobe com `app.run(debug=True, host='0.0.0.0', port=5000)`:

- `debug=True` liga o *reloader*: alterações no arquivo reiniciam o processo.
- `host='0.0.0.0'` aceita conexões de outras máquinas/WSL.
- **Não é um servidor de produção** e não tem autenticação. Use apenas em
  rede local/confiável.

---

## 3. Configuração

### 3.1 Arquivo `.env` e variáveis de ambiente

Na inicialização, `_load_env_file()` procura, nesta ordem:

1. `backend/.env`
2. `.env` na raiz do projeto

O **primeiro arquivo existente** é carregado e os demais são ignorados. A
leitura usa `python-dotenv` com `override=False` (variáveis já definidas no
ambiente têm prioridade). Se `python-dotenv` não estiver instalado, há um
parser simples que também aceita linhas no formato `set VAR=valor` (útil no
PowerShell).

| Variável | Obrigatória | Efeito |
| --- | --- | --- |
| `SPOTIFY_CLIENT_ID` | para buscar no Spotify | Client ID do app no dashboard do Spotify |
| `SPOTIFY_CLIENT_SECRET` | para buscar no Spotify | Client Secret do app |
| `YT_COOKIES_FILE` | não | Caminho de um `cookies.txt` para o `yt-dlp` |
| `YT_COOKIES_BROWSER` | não | Navegador de onde ler cookies (`chrome`, `firefox`, `edge`, `brave`...) |

`YT_COOKIES_FILE` tem prioridade sobre `YT_COOKIES_BROWSER`. Use apenas um dos
dois, e só quando o YouTube retornar `HTTP 403` ou pedir login.

Se `SPOTIFY_CLIENT_ID` estiver vazio ou for um dos placeholders
(`sua_chave_api`, `SEU_CLIENT_ID_AQUI`), o Spotify fica desabilitado: o
`/health` responde `spotify_enabled: false` e `/search/spotify` retorna `503`.
O restante do backend (download por texto, análise, upload) continua
funcionando.

Modelo pronto: `backend/.env.example`. O `backend/.env` é ignorado pelo Git.

### 3.2 Constantes internas

| Constante | Valor | Uso |
| --- | --- | --- |
| `UPLOAD_FOLDER` | pasta temporária do sistema | destino dos uploads de `/analyze` |
| `AUDIO_CACHE_FOLDER` | `<temp>/guitar_hero_cache` | MP3 baixados e reaproveitados |
| `ALLOWED_EXTENSIONS` | `mp3`, `wav`, `ogg`, `flac`, `m4a` | validação do upload |
| `MAX_FILE_SIZE` | 50 MiB | limite do corpo do upload (HTTP 413 acima disso) |
| `SPOTIFY_REQUEST_TIMEOUT` | 10 s | timeout de cada requisição ao Spotify |
| `SPOTIFY_SEARCH_ATTEMPTS` | 3 | tentativas por busca no Spotify |
| `SPOTIFY_SEARCH_RETRY_DELAY` | 0,5 s | pausa entre tentativas |
| `audio_cache` | dicionário em memória | metadados de cada `cache_id` baixado |

No Windows, `<temp>` costuma ser `C:\Users\<usuário>\AppData\Local\Temp`; no
WSL/Linux, `/tmp`.

---

## 4. Endpoints

| Método | Rota | Função |
| --- | --- | --- |
| `GET` | `/health` | status da API e do Spotify |
| `GET` | `/search/spotify?q=...&limit=...` | busca de faixas no Spotify |
| `POST` | `/analyze/youtube` | baixa do YouTube e gera a chart |
| `GET` | `/stream/<cache_id>` | serve o MP3 em cache |
| `POST` | `/analyze` | analisa um arquivo enviado por upload |

As rotas do backend respondem erro no formato abaixo. Exceções: `413`
(corpo maior que 50 MiB) é gerado pelo próprio Flask, e rotas inexistentes usam
o `404` padrão.

```json
{ "success": false, "error": "mensagem" }
```

### 4.1 `GET /health`

```json
{
  "status": "online",
  "message": "Guitar Hero Backend v3 - Spotify + YouTube!",
  "version": "3.0",
  "spotify_enabled": true
}
```

### 4.2 `GET /search/spotify`

| Parâmetro | Padrão | Descrição |
| --- | --- | --- |
| `q` | — | termo de busca (obrigatório) |
| `limit` | `10` | número de faixas (inteiro) |

Resposta `200`:

```json
{
  "success": true,
  "tracks": [
    {
      "id": "3n3Ppam7vgaVa1iaRUc9Lp",
      "name": "Mr. Brightside",
      "artist": "The Killers",
      "album": "Hot Fuss",
      "image": "https://i.scdn.co/image/...",
      "preview_url": "https://p.scdn.co/mp3-preview/...",
      "duration_ms": 222973,
      "spotify_url": "https://open.spotify.com/track/..."
    }
  ]
}
```

Códigos: `400` sem `q`, `503` Spotify não configurado, `500` erro da API.

O backend usa apenas o *Client Credentials* do Spotify: não acessa a conta do
usuário, playlists ou histórico. `preview_url` é o trecho de 30 s (pode vir
`null`).

A busca usa **10 s de timeout por requisição** e tenta até **3 vezes** (com
0,5 s entre tentativas) quando ocorre erro de rede/DNS ou erro da API do
Spotify. Isso absorve engasgos típicos de conexões móveis: a primeira tentativa
pode falhar e a segunda já retornar os resultados. Se todas falharem, a
resposta é `500` com a última exceção. O token de acesso é guardado pelo
`spotipy` em `backend/.cache` (válido por ~1 h), então as buscas seguintes
geralmente fazem só uma requisição.

> A mensagem `✅ Spotify API conectada!` no startup indica apenas que as
> credenciais foram lidas; ela não faz teste de rede.

### 4.3 `POST /analyze/youtube`

Corpo JSON:

```json
{ "query": "Grupo 100% - Hoje eu vou pagodear", "difficulty": "easy" }
```

- `query` é obrigatório (`400` se faltar).
- `difficulty`: `easy` | `medium` | `hard` | `expert` (padrão `medium`).
  Um valor desconhecido usa a configuração de `medium`, mas o campo
  `audio_info.difficulty` ecoa o valor recebido.

Resposta `200`:

```json
{
  "success": true,
  "audio_info": {
    "duration": 362.84,
    "tempo": 152.0,
    "beats_count": 915,
    "onsets_count": 1411,
    "notes_count": 540,
    "hold_notes_count": 61,
    "difficulty": "easy",
    "sample_rate": 22050
  },
  "notes": [
    { "id": 0, "time": 1.25, "lane": 2, "type": "tap", "duration": 0.0 },
    { "id": 1, "time": 2.04, "lane": 0, "type": "hold", "duration": 0.72 }
  ],
  "cache_id": "8d25e5021215a9f2c683bcde64f242b0",
  "audio_url": "/stream/8d25e5021215a9f2c683bcde64f242b0"
}
```

Códigos: `400` sem `query`, `500` falha no download ou na análise.

O `cache_id` é o **MD5 da `query`** — a mesma string sempre aponta para o mesmo
arquivo. Se o MP3 já existe e é válido, o download é pulado, mas **a análise é
refeita** a cada requisição (a chart não fica em cache).

### 4.4 `GET /stream/<cache_id>`

Devolve o MP3 (`audio/mpeg`) com suporte a *range requests* (o `send_file` do
Flask/Werkzeug trata `Range` automaticamente, permitindo seek).

O caminho é resolvido primeiro pelo dicionário `audio_cache` e, se o processo
tiver reiniciado, pelo arquivo `<AUDIO_CACHE_FOLDER>/<cache_id>.mp3`. Ou seja:
o áudio sobrevive a reinícios; o dicionário não.

Códigos: `404` se o arquivo não existir, `500` em erro inesperado.

### 4.5 `POST /analyze`

Upload `multipart/form-data`:

| Campo | Descrição |
| --- | --- |
| `file` | áudio (`.mp3`, `.wav`, `.ogg`, `.flac`, `.m4a`) |
| `difficulty` | `easy`/`medium`/`hard`/`expert` (padrão `medium`) |

O arquivo é salvo com `secure_filename` na pasta temporária, analisado e
**apagado em seguida** (inclusive quando a análise falha). A resposta é igual à
do `/analyze/youtube`, porém sem `cache_id` e `audio_url`.

Códigos: `400` (sem arquivo, nome vazio ou extensão inválida), `500` (erro na
análise), `413` (acima de 50 MiB).

### 4.6 Exemplos rápidos

```powershell
# PowerShell
Invoke-RestMethod http://127.0.0.1:5000/health
Invoke-RestMethod "http://127.0.0.1:5000/search/spotify?q=legiao+urbana&limit=5"
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/analyze/youtube `
  -ContentType "application/json" `
  -Body '{"query":"Grupo 100% - Hoje eu vou pagodear","difficulty":"easy"}'
```

```bash
# WSL / Linux
curl http://127.0.0.1:5000/health
curl "http://127.0.0.1:5000/search/spotify?q=legiao+urbana&limit=5"
curl -X POST http://127.0.0.1:5000/analyze/youtube \
  -H "Content-Type: application/json" \
  -d '{"query":"Grupo 100% - Hoje eu vou pagodear","difficulty":"easy"}'
```

---

## 5. Download do YouTube

### 5.1 Cache e concorrência

- `cache_id = md5(query)`; o arquivo fica em
  `<AUDIO_CACHE_FOLDER>/<cache_id>.mp3`.
- O cache só é considerado válido se o arquivo existir e tiver **mais de
  64 KB** (`_valid_cached_audio`). Isso evita reaproveitar download truncado.
- O download da mesma `query` é **serializado** por um lock em memória
  (`_download_lock`): se duas requisições pedirem a mesma música ao mesmo
  tempo, uma baixa e a outra espera e reaproveita o arquivo. Músicas diferentes
  podem baixar em paralelo.
- Ao final de cada tentativa, o backend confere se o MP3 válido já está no
  disco. Se uma tentativa falhar depois de criar o arquivo (por exemplo,
  `WinError 5` no rename do `.m4a` no Windows), o MP3 é reaproveitado em vez de
  retornar erro.
- Arquivos parciais (`<cache_id>.*` que não terminam em `.mp3`) são removidos
  entre as tentativas.

### 5.2 Busca do vídeo

Primeiro o `yt-dlp` roda em modo `extract_flat` com `ytsearch1:<query>` para
descobrir a URL do vídeo sem baixar. Se nenhum resultado for encontrado, a
função retorna `(None, None)`.

### 5.3 Tentativas de download

O YouTube bloqueia alguns *player clients* (403 / PO token). O backend tenta,
em ordem, até um funcionar:

| # | `player_client` | `format` |
| --- | --- | --- |
| 1 | padrão do yt-dlp | `bestaudio[ext=m4a]/bestaudio/best` |
| 2 | `android_vr` | `bestaudio[ext=m4a]/bestaudio/best` |
| 3 | `tv` | `bestaudio/best` |
| 4 | `android_vr` + `tv` | `best` |

Opções relevantes de `_build_ydl_opts`:

| Opção | Valor | Motivo |
| --- | --- | --- |
| pós-processador | `FFmpegExtractAudio` → `mp3`, 192 kbps | formato que o SDL_mixer abre |
| `http_chunk_size` | 10 MiB | reduz 403 por throttling do googlevideo |
| `js_runtimes` | `deno`, `node` | solver JS exigido pelo YouTube |
| `remote_components` | `ejs:github` | solver EJS remoto |
| `retries` / `fragment_retries` | 3 | tolerância a falhas de rede |
| `socket_timeout` | 20 s | evita travar em conexão morta |
| `noplaylist` | `True` | `ytsearch1` deve trazer um vídeo só |

Se as quatro tentativas falharem, o backend ainda verifica o cache uma última
vez antes de responder erro. As mensagens de ajuda no log sugerem atualizar o
`yt-dlp`, instalar Deno ou configurar cookies.

---

## 6. Análise de áudio

`analyze_audio(file_path, difficulty)`:

1. `librosa.load(file_path, sr=22050)` — mono, 22,05 kHz.
2. `librosa.get_duration` — duração em segundos.
3. `librosa.beat.beat_track` — BPM estimado e tempos de batida.
4. `librosa.onset.onset_detect(backtrack=True)` — inícios de nota.
5. `librosa.feature.spectral_centroid` — "brilho" do som por frame.
6. `librosa.feature.chroma_cqt` — energia por classe de altura (12 pitches).
7. `generate_notes_with_duration(...)` — converte tudo em notas.
8. Monta `audio_info` e devolve `{success, audio_info, notes}`.

Observações:

- A análise é **síncrona e pesada** (librosa): normalmente de 20 a 90 segundos
  para uma música de 4 a 6 minutos. Por isso o cliente usa uma thread.
- `hold_notes_count` em `audio_info` conta notas com `duration > 0.3`
  (não necessariamente `type == "hold"`).
- Em caso de exceção, retorna `{success: false, error: "..."}` e imprime o
  traceback no console.

---

## 7. Geração da chart

### 7.1 Configuração por dificuldade

| Dificuldade | Usa beats | Usa onsets | `density` | Lanes | Chance de hold | Hold mínimo | Gap mínimo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `easy` | sim | não | 0.7 | 3 | 12% | 0.50 s | 0.40 s |
| `medium` | sim | sim | 0.6 | 4 | 25% | 0.35 s | 0.25 s |
| `hard` | sim | sim | 0.75 | 5 | 30% | 0.30 s | 0.20 s |
| `expert` | sim | sim | 0.9 | 5 | 35% | 0.25 s | 0.15 s |

### 7.2 Passo a passo

1. **Junta os tempos**: beats (todas) + onsets (`medium` em diante).
2. **Deduplica**: arredonda para 3 casas, remove repetidos e ordena.
3. **Filtra por gap**: percorre em ordem e mantém um tempo só se ele estiver a
   pelo menos `min_time_gap` do último mantido.
4. **Aplica densidade**: `step = max(1, int(1 / density))`. Com os valores
   atuais, `int(1/density)` é `1` nas quatro dificuldades, então esse passo não
   remove nada — a densidade real vem do gap mínimo e do uso de onsets.
5. **Corta as bordas**: ignora notas antes de **1,0 s** e para em
   **`duração - 2,0 s`**.
6. **Escolhe a lane** de cada nota (ver 7.3).
7. **Decide hold ou tap** (ver 7.4).
8. Devolve a lista de notas em ordem de tempo.

### 7.3 Escolha da lane

- Pega a coluna de chroma correspondente ao instante (índice proporcional ao
  tempo, limitado ao número de colunas).
- Escolhe a classe de altura (pitch) com mais energia e calcula
  `lane = pitch_dominante % num_lanes`.
- **Balanceamento**: se a lane escolhida já tem mais de `média + 2` notas, usa a
  lane com menos notas.
- Em **30% das notas**, a lane é trocada por uma posição derivada do
  `spectral_centroid` normalizado (som mais agudo tende a lanes mais altas).
- O valor final é limitado a `[0, num_lanes - 1]`.

### 7.4 Hold notes

- Sorteio com `hold_probability` (12% a 35%).
- Se sorteado, `detect_note_duration` mede a duração pela energia RMS:
  - RMS com `frame_length=2048`, `hop_length=512`;
  - limiar de 30% da energia no instante do onset;
  - conta frames consecutivos acima do limiar, até no máximo 2,5 s;
  - resultado limitado a `[0.1, 2.5]` segundos.
- Se a duração medida for menor que `min_hold_duration`, a nota vira `tap`.

### 7.5 Formato da nota

```json
{ "id": 0, "time": 1.25, "lane": 2, "type": "tap", "duration": 0.0 }
```

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `id` | int | sequencial, na ordem de geração |
| `time` | float | instante em segundos (3 casas) |
| `lane` | int | `0` a `num_lanes - 1` |
| `type` | string | `tap` ou `hold` |
| `duration` | float | segundos do hold; `0.0` para tap |

O cliente ainda passa essa lista por `chart.prepare_notes`, que impõe um gap
mínimo **por lane**, encurta holds que invadem a próxima nota do mesmo lane e
limita a 2 notas simultâneas (acorde).

### 7.6 Cobertura de início/fim

A grade usa apenas beats/onsets detectados. Em músicas com introdução ou final
sem percussão, o detector pode não encontrar batidas nesses trechos, e a chart
fica sem notas até onde houver batida (respeitando o corte de 1,0 s no início e
2,0 s no fim). Se for necessário cobrir esses trechos, o ponto de mudança é
`generate_notes_with_duration`, logo após o cálculo de `selected_times`.

---

## 8. Cache e arquivos temporários

| Caminho | Conteúdo | Persistência |
| --- | --- | --- |
| `<temp>/guitar_hero_cache/<cache_id>.mp3` | áudio baixado do YouTube | sobrevive a reinícios |
| `<temp>/guitar_hero_cache/<cache_id>.*` | partes temporárias do download | removidas após falha |
| `<temp>/<nome-do-upload>` | upload de `/analyze` | apagado após a análise |
| `audio_cache` (memória) | metadados por `cache_id` | perdido ao reiniciar |

Para limpar tudo, pare o backend e apague a pasta `guitar_hero_cache`.

---

## 9. Logs

O backend imprime logs com emoji no console. Linhas comuns:

| Log | Significado |
| --- | --- |
| `✅ Spotify API conectada!` | credenciais lidas (não testa a rede) |
| `⚠️ Busca no Spotify falhou (tentativa N/3)` | erro de rede/DNS; nova tentativa em 0,5 s |
| `♻️ Usando áudio do cache` | MP3 válido reaproveitado |
| `🔍 Buscando no YouTube` / `📹 Vídeo encontrado` | busca de metadados |
| `📥 Tentativa N/4` | início de uma tentativa de download |
| `⚠️ Tentativa N falhou` | tentativa falhou (403, rename etc.) |
| `✅ Áudio íntegro já estava no cache após a falha` | fallback do cache |
| `✅ Download completo` | MP3 criado e validado |
| `Carregando áudio` / `Duração` | início da análise |
| `BPM detectado` / `Onsets detectados` | features extraídas |
| `Gerando notas - Tempos totais / Filtrados / Selecionados` | funil da chart |
| `Notas geradas` / `Distribuição por lane` | resultado da chart |
| `✅ Análise completa! Stream URL: ...` | resposta `200` pronta |
| `❌ Todas as tentativas falharam` | download impossível |

Defina `PYTHONIOENCODING=utf-8` para evitar `UnicodeEncodeError` no Windows.

---

## 10. Limitações e cuidados

- **Sem autenticação** e com `host='0.0.0.0'`: não exponha na internet.
- **Servidor de desenvolvimento** (`debug=True`); para produção use um WSGI
  (waitress/gunicorn) e desligue o debug.
- **Análise não é cacheada**: cada `/analyze/youtube` refaz beats/onsets/chroma,
  mesmo com o MP3 em cache.
- **Spotify** só retorna faixas (`type='track'`), com o `limit` pedido; não há
  paginação.
- **YouTube** muda com frequência: mantenha `yt-dlp` atualizado e, se houver
  403 persistente, configure cookies.
- **Credenciais**: `backend/.env` é ignorado pelo Git. Se um Client Secret já
  foi exposto, gere outro no dashboard do Spotify.

---

## 11. Referência de funções

| Função | Papel |
| --- | --- |
| `_load_env_file()` | carrega `backend/.env` ou `.env` da raiz |
| `allowed_file(name)` | valida a extensão do upload |
| `_build_ydl_opts(outtmpl, clients, fmt)` | monta as opções do `yt-dlp` por tentativa |
| `_cleanup_partial_files(cache_id)` | apaga partes temporárias do download |
| `_valid_cached_audio(path)` | valida o MP3 em cache (> 64 KB) |
| `_download_lock(cache_id)` | lock por música contra downloads simultâneos |
| `search_youtube_and_download(query, use_cache=True)` | cache + lock + download |
| `_download_from_youtube(query, cache_id, cached_path)` | busca, tenta 4 clients e valida |
| `detect_note_duration(y, sr, onset_time, max_duration)` | duração de hold por RMS |
| `analyze_audio(file_path, difficulty)` | pipeline do librosa + chart |
| `generate_notes_with_duration(...)` | converte features em notas |
| `health_check()` | `GET /health` |
| `search_spotify()` | `GET /search/spotify` |
| `analyze_from_youtube()` | `POST /analyze/youtube` |
| `stream_audio(cache_id)` | `GET /stream/<cache_id>` |
| `analyze()` | `POST /analyze` (upload) |
