# Guitar Clone Web

Clone de Guitar Hero com backend Flask, frontend React e um cliente desktop em
PyGame. O backend busca músicas no Spotify, baixa o áudio do YouTube, analisa o
áudio e gera a chart automaticamente.

```
backend/        API Flask (busca Spotify, download YouTube, análise, chart, cache)
frontend/       interface web em React + Vite
pygame-client/  cliente desktop em PyGame (jogo completo)
```

Este guia cobre **PowerShell (Windows)** e **WSL (Ubuntu/Debian)**.

> Nos comandos abaixo, troque `C:\Projetos-Pessoais\guitar-clone-web` e
> `~/guitar-clone-web` pelo caminho do seu clone. Os exemplos usam `python`; se
> você usa o launcher do Windows, pode trocar por `py -3`.

---

## Início rápido (só o jogo, sem backend)

A demo gera a música e a chart localmente, sem Spotify, YouTube ou internet.

### PowerShell

```powershell
cd C:\Projetos-Pessoais\guitar-clone-web\pygame-client
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --demo
```

### WSL

```bash
cd ~/guitar-clone-web/pygame-client
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --demo
```

Para o jogo completo (busca Spotify + download YouTube), siga as seções do
backend e do cliente abaixo.

---

## Requisitos

| Ferramenta | Versão | Para quê |
| --- | --- | --- |
| Python | 3.10+ | backend e cliente PyGame |
| Node.js | 20+ | frontend e solver JS do yt-dlp |
| ffmpeg | qualquer recente | conversão de áudio do YouTube |
| Deno | opcional | solver EJS do yt-dlp (alternativa ao Node) |

O backend escuta em `http://127.0.0.1:5000` (bind `0.0.0.0:5000`), o frontend
Vite em `http://localhost:5173` e o cliente PyGame consome a API na porta 5000.

---

## 1. Configurar as credenciais do Spotify

Crie um app em <https://developer.spotify.com/dashboard> e use as credenciais
via variáveis de ambiente. **Nunca comite `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`.**

### PowerShell

```powershell
$env:SPOTIFY_CLIENT_ID = "seu_client_id"
$env:SPOTIFY_CLIENT_SECRET = "seu_client_secret"
```

Para deixar permanente no usuário:

```powershell
[Environment]::SetEnvironmentVariable("SPOTIFY_CLIENT_ID", "seu_client_id", "User")
[Environment]::SetEnvironmentVariable("SPOTIFY_CLIENT_SECRET", "seu_client_secret", "User")
```

### WSL / Linux

```bash
export SPOTIFY_CLIENT_ID="seu_client_id"
export SPOTIFY_CLIENT_SECRET="seu_client_secret"
```

Para deixar permanente, adicione as duas linhas ao final de `~/.bashrc`.

> Sem Spotify configurado o backend sobe normalmente, mas a busca fica
> desabilitada. Nesse caso use a **demo** (`F2`) ou envie um arquivo local (`U`).

---

## 2. Instalar dependências

### PowerShell (Windows)

```powershell
cd C:\Projetos-Pessoais\guitar-clone-web

# backend
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
deactivate

# cliente PyGame
python -m venv pygame-client\.venv
.\pygame-client\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r pygame-client\requirements.txt
deactivate

# frontend (opcional)
cd frontend
npm install
cd ..
```

Se o PowerShell bloquear a ativação do venv:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Instale o ffmpeg (necessário para o yt-dlp converter o áudio):

```powershell
winget install Gyan.FFmpeg
# ou: choco install ffmpeg
```

### WSL (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg libsndfile1

# prefira clonar/copiar para o filesystem do Linux: /mnt/c é lento para venv
cd ~/guitar-clone-web

python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
deactivate

python3 -m venv pygame-client/.venv
source pygame-client/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r pygame-client/requirements.txt
deactivate

# frontend (opcional)
cd frontend
npm install
cd ..
```

O `yt-dlp` atual precisa de um runtime JS para o YouTube. Instale **Node.js 20+**
(por exemplo via [nvm](https://github.com/nvm-sh/nvm) ou Nodesource) ou **Deno**
e garanta que o comando (`node` ou `deno`) esteja no `PATH` do processo do backend.

---

## 3. Rodar o backend (Flask)

O backend imprime emojis no console. No Windows, sem `PYTHONIOENCODING=utf-8`,
ele pode encerrar com `UnicodeEncodeError`.

### PowerShell — terminal 1

```powershell
cd C:\Projetos-Pessoais\guitar-clone-web\backend
$env:PYTHONIOENCODING = "utf-8"
$env:SPOTIFY_CLIENT_ID = "seu_client_id"
$env:SPOTIFY_CLIENT_SECRET = "seu_client_secret"
.\.venv\Scripts\python.exe guitar-clone-back.py
```

### WSL — terminal 1

```bash
cd ~/guitar-clone-web/backend
export PYTHONIOENCODING=utf-8
export SPOTIFY_CLIENT_ID="seu_client_id"
export SPOTIFY_CLIENT_SECRET="seu_client_secret"
.venv/bin/python guitar-clone-back.py
```

Teste rápido em outro terminal:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health -UseBasicParsing
```

```bash
curl http://127.0.0.1:5000/health
```

Se a porta 5000 já estiver em uso, encerre o processo antigo antes de subir outro
backend.

---

## 4. Rodar o cliente PyGame

### PowerShell — terminal 2

```powershell
cd C:\Projetos-Pessoais\guitar-clone-web\pygame-client
.\.venv\Scripts\python.exe main.py
```

Atalho equivalente:

```powershell
.\run.bat
```

### WSL — terminal 2

```bash
cd ~/guitar-clone-web/pygame-client
.venv/bin/python main.py
```

Em Windows 11 com WSL2 + WSLg a janela e o áudio funcionam direto. No Windows 10
é necessário um servidor X e PulseAudio; nesse caso é mais simples rodar o
cliente no Windows e deixar o backend no WSL (veja abaixo).

### Opções do cliente

```bash
python main.py --demo                          # demo local, sem backend/internet
python main.py --backend http://127.0.0.1:5000 # backend em outra porta/máquina
python main.py --headless                      # testes sem janela (SDL dummy)
```

Também é possível definir `GUITAR_BACKEND_URL` em vez de `--backend`.

### Backend no WSL + cliente no Windows

1. No WSL, suba o backend normalmente (`host='0.0.0.0'`).
2. No PowerShell:

```powershell
cd C:\Projetos-Pessoais\guitar-clone-web\pygame-client
.\.venv\Scripts\python.exe main.py --backend http://127.0.0.1:5000
```

O WSL2 faz o encaminhamento de `localhost` para os serviços Linux. Se não
funcionar, use o IP do WSL (`ip addr show eth0` dentro do WSL) e libere a porta no
firewall do Windows.

---

## 5. Rodar o frontend React (opcional)

Com o backend rodando:

```powershell
cd C:\Projetos-Pessoais\guitar-clone-web\frontend
npm run dev
```

```bash
cd ~/guitar-clone-web/frontend
npm run dev
```

Abra <http://localhost:5173>. O frontend usa `http://localhost:5000` como backend
fixo em `frontend/src/App.jsx`.

---

## 6. Modo demo e upload local

- **Demo:** `python main.py --demo` ou pressione `F2` na tela de busca. Gera uma
  faixa e uma chart locais, sem backend.
- **Upload:** pressione `U` na tela de busca ou arraste um arquivo de áudio
  (`.mp3`, `.wav`, `.ogg`, `.flac`, `.m4a`) sobre a janela.
- **Spotify:** digite na busca e pressione `ENTER`.

O primeiro download/analise pode demorar (yt-dlp + librosa). Depois o áudio fica
em cache (`pygame-client/cache/` e a pasta temporária do sistema,
`guitar_hero_cache`).

---

## 7. Variáveis de ambiente

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SPOTIFY_CLIENT_ID` | — | Client ID do app Spotify |
| `SPOTIFY_CLIENT_SECRET` | — | Client Secret do app Spotify |
| `YT_COOKIES_FILE` | — | Caminho de um `cookies.txt` para o yt-dlp |
| `YT_COOKIES_BROWSER` | — | Navegador de onde ler cookies (`chrome`, `firefox`, `edge`, `brave`) |
| `GUITAR_BACKEND_URL` | `http://127.0.0.1:5000` | URL do backend usada pelo cliente PyGame |
| `PYTHONIOENCODING` | — | Use `utf-8` no Windows para o backend |

Exemplo com cookies do YouTube (quando aparece `HTTP 403: Forbidden`):

```powershell
$env:YT_COOKIES_BROWSER = "chrome"
# ou: $env:YT_COOKIES_FILE = "C:\caminho\cookies.txt"
```

```bash
export YT_COOKIES_BROWSER="chrome"
# ou: export YT_COOKIES_FILE="$HOME/cookies.txt"
```

No WSL, `YT_COOKIES_BROWSER` não enxerga o Chrome do Windows; exporte um
`cookies.txt` no navegador e use `YT_COOKIES_FILE`.

---

## 8. Controles do jogo

| Tela | Tecla | Ação |
| --- | --- | --- |
| Busca | digitar + `ENTER` | buscar no Spotify |
| Busca | `U` | escolher arquivo local |
| Busca | `F2` | iniciar demo |
| Busca | `1`–`4` | dificuldade (fácil/médio/difícil/expert) |
| Busca | setas + `ENTER` | navegar e jogar |
| Jogo | `A S D J K` ou `1 2 3 4 5` | lanes (3/4/5 conforme dificuldade) |
| Jogo | `ESPAÇO` | começar |
| Jogo | `ESC` / `P` | pausar/continuar |
| Pausa | `R` | reiniciar |
| Pausa | `M` | voltar à busca |
| Resultados | `R` / `ENTER` | jogar de novo |
| Resultados | `N` / `ESC` | nova música |

`F11` alterna tela cheia.

---

## 9. Problemas comuns

| Sintoma | Causa / solução |
| --- | --- |
| `UnicodeEncodeError` no backend | Defina `PYTHONIOENCODING=utf-8` antes de rodar |
| `HTTP 403: Forbidden` no download | YouTube bloqueando acesso anônimo: configure `YT_COOKIES_FILE`/`YT_COOKIES_BROWSER`, ou use upload/demo |
| Busca retorna erro | Spotify não configurado ou credenciais inválidas |
| Porta 5000 ocupada | Encerre o processo antigo (`Get-NetTCPConnection -LocalPort 5000` no PowerShell, `lsof -i :5000` no WSL) |
| Sem áudio no WSL | Verifique WSLg (Windows 11) ou rode o cliente no Windows apontando para o backend no WSL |
| Janela não abre no WSL | Windows 10 exige X server; prefira Windows 11/WSLg ou rode o cliente no Windows |
| Sem som em `.m4a`/`.flac` | Instale o `ffmpeg` e confirme que está no `PATH` |

Logs de falha do cliente ficam em `pygame-client/crash.log`.

---

## 10. Documentação específica

- `pygame-client/README.md` — detalhes do cliente desktop, estrutura e ajustes.
- `frontend/README.md` — template padrão do Vite/React.

## Aviso sobre credenciais

As credenciais do Spotify são lidas de variáveis de ambiente e nunca devem ser
commitadas. Se você já expôs um Client Secret em algum commit, gere um novo no
dashboard do Spotify e atualize suas variáveis locais.
