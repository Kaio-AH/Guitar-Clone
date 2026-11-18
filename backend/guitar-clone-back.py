"""
Guitar Hero Backend - v3
Sistema com Spotify + YouTube
Busca músicas no Spotify e baixa áudio do YouTube
AGORA COM STREAMING DE ÁUDIO!

Requisitos:
pip install flask flask-cors librosa numpy soundfile spotipy yt-dlp

Configuração:
1. Crie um app em: https://developer.spotify.com/dashboard
2. Adicione Redirect URI: http://127.0.0.1:5000/callback
3. Copie Client ID e Client Secret
4. Defina as variáveis de ambiente SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET
   (nunca comite credenciais reais no código)

Uso:
python guitar_hero_backend_v3.py
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import librosa
import numpy as np
import os
import json
from werkzeug.utils import secure_filename
import tempfile
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import re
import hashlib
import time
import threading


def _load_env_file() -> None:
    """Carrega backend/.env (ou .env na raiz) sem sobrescrever o ambiente."""
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = (os.path.join(base, '.env'), os.path.join(os.path.dirname(base), '.env'))
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            from dotenv import load_dotenv
        except ImportError:
            load_dotenv = None
        if load_dotenv is not None:
            load_dotenv(path, override=False)
        else:
            # Fallback simples caso python-dotenv nao esteja instalado.
            try:
                with open(path, 'r', encoding='utf-8-sig') as handle:
                    for raw in handle:
                        line = raw.strip()
                        if line.lower().startswith('set '):
                            line = line[4:].strip()
                        if not line or line.startswith('#') or '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value
            except OSError:
                pass
        break


_load_env_file()

app = Flask(__name__)
CORS(app)

# ============================================================
# CONFIGURACAO DO SPOTIFY - use variaveis de ambiente ou backend/.env
#   SPOTIFY_CLIENT_ID=...
#   SPOTIFY_CLIENT_SECRET=...
# ============================================================
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', 'sua_chave_api')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', 'seu_client_secret_id')

# Configurações gerais
UPLOAD_FOLDER = tempfile.gettempdir()
AUDIO_CACHE_FOLDER = os.path.join(tempfile.gettempdir(), 'guitar_hero_cache')
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac', 'm4a'}
MAX_FILE_SIZE = 50 * 1024 * 1024

# Cria pasta de cache se não existir
os.makedirs(AUDIO_CACHE_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Cache de áudios baixados (query -> filepath)
audio_cache = {}

# Inicializa Spotify Client
try:
    if SPOTIFY_CLIENT_ID not in ('', 'sua_chave_api', 'SEU_CLIENT_ID_AQUI'):
        spotify = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
        sp = spotipy.Spotify(client_credentials_manager=spotify)
        SPOTIFY_ENABLED = True
        print("✅ Spotify API conectada!")
    else:
        SPOTIFY_ENABLED = False
        print("⚠️  Spotify não configurado. Configure SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET")
except Exception as e:
    SPOTIFY_ENABLED = False
    print(f"⚠️  Erro ao conectar Spotify: {e}")


def allowed_file(filename):
    """Verifica se o arquivo tem uma extensão permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _build_ydl_opts(outtmpl, player_clients, fmt):
    """Monta as opções do yt-dlp para uma tentativa específica"""
    opts = {
        'format': fmt,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': outtmpl,
        'quiet': False,
        'no_warnings': False,
        'noplaylist': True,
        'nocheckcertificate': True,
        'retries': 3,
        'fragment_retries': 3,
        'socket_timeout': 20,
        # Baixar em pedaços evita 403 por throttling do googlevideo
        'http_chunk_size': 10 * 1024 * 1024,
        # Runtime JS (Deno) + solver EJS: exigidos pelo YouTube em 2026
        'js_runtimes': {'deno': {}, 'node': {}},
        'remote_components': ['ejs:github'],
    }
    # player_clients=None -> deixa o yt-dlp escolher os clients padrão (recomendado)
    if player_clients:
        opts['extractor_args'] = {'youtube': {'player_client': player_clients}}

    # Cookies (opcional, ajuda com 403 persistente e vídeos com restrição)
    #   export YT_COOKIES_FILE=/caminho/cookies.txt
    #   export YT_COOKIES_BROWSER=chrome   (ou firefox, edge, brave...)
    cookies_file = os.environ.get('YT_COOKIES_FILE')
    cookies_browser = os.environ.get('YT_COOKIES_BROWSER')
    if cookies_file and os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file
    elif cookies_browser:
        opts['cookiesfrombrowser'] = (cookies_browser,)

    return opts


def _cleanup_partial_files(cache_id):
    """Remove arquivos parciais/temporários de uma tentativa que falhou"""
    try:
        for name in os.listdir(AUDIO_CACHE_FOLDER):
            if name.startswith(cache_id) and not name.endswith('.mp3'):
                os.remove(os.path.join(AUDIO_CACHE_FOLDER, name))
    except Exception:
        pass


def _valid_cached_audio(path):
    """Retorna True se o mp3 existe e tem tamanho plausivel."""
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 64 * 1024
    except OSError:
        return False


_download_locks = {}
_download_locks_guard = threading.Lock()


def _download_lock(cache_id):
    """Lock por cache_id: evita dois downloads simultaneos da mesma consulta."""
    with _download_locks_guard:
        lock = _download_locks.get(cache_id)
        if lock is None:
            lock = threading.Lock()
            _download_locks[cache_id] = lock
        return lock


def search_youtube_and_download(query, use_cache=True):
    """
    Busca e baixa áudio do YouTube com sistema de cache.
    Tenta vários player clients do yt-dlp em sequência, porque o YouTube
    bloqueia (403) alguns clients (web/web_safari exigem PO token / SABR).

    Args:
        query: string de busca (ex: "Queen - Bohemian Rhapsody")
        use_cache: usar cache de downloads anteriores

    Returns:
        (filepath, cache_id) ou (None, None) se falhar
    """
    cache_id = hashlib.md5(query.encode()).hexdigest()
    cached_path = os.path.join(AUDIO_CACHE_FOLDER, f"{cache_id}.mp3")

    if use_cache and _valid_cached_audio(cached_path):
        print(f"♻️  Usando áudio do cache: {query}")
        return cached_path, cache_id

    # Serializa downloads da mesma consulta: se duas requisicoes chegarem
    # juntas, a segunda espera e reaproveita o arquivo da primeira.
    with _download_lock(cache_id):
        if use_cache and _valid_cached_audio(cached_path):
            print(f"♻️  Usando áudio do cache: {query}")
            return cached_path, cache_id
        return _download_from_youtube(query, cache_id, cached_path)


def _download_from_youtube(query, cache_id, cached_path):
    outtmpl = cached_path.replace('.mp3', '.%(ext)s')

    # 1) Busca só os metadados (sem baixar) para obter a URL do vídeo
    try:
        print(f"🔍 Buscando no YouTube: {query}")
        search_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            result = ydl.extract_info(f"ytsearch1:{query}", download=False)
        entries = (result or {}).get('entries') or []
        if not entries:
            print("❌ Nenhum resultado encontrado no YouTube")
            return None, None
        video_url = entries[0].get('url') or f"https://www.youtube.com/watch?v={entries[0]['id']}"
        print(f"📹 Vídeo encontrado: {entries[0].get('title', 'N/A')} -> {video_url}")
    except Exception as e:
        print(f"❌ Erro na busca do YouTube: {e}")
        return None, None

    # 2) Tenta baixar com diferentes clients/formatos até um funcionar
    attempts = [
        (None,                 'bestaudio[ext=m4a]/bestaudio/best'),  # padrão do yt-dlp
        (['android_vr'],       'bestaudio[ext=m4a]/bestaudio/best'),
        (['tv'],               'bestaudio/best'),
        (['android_vr', 'tv'], 'best'),   # último recurso
    ]

    last_error = None
    for i, (clients, fmt) in enumerate(attempts, 1):
        try:
            print(f"📥 Tentativa {i}/{len(attempts)} (clients={clients or 'padrão'}, format={fmt})")
            with yt_dlp.YoutubeDL(_build_ydl_opts(outtmpl, clients, fmt)) as ydl:
                info = ydl.extract_info(video_url, download=True)

            if _valid_cached_audio(cached_path):
                file_size = os.path.getsize(cached_path) / (1024 * 1024)
                title = info.get('title', query)
                print(f"✅ Download completo: {title}")
                print(f"   - Cache ID: {cache_id}")
                print(f"   - Tamanho: {file_size:.2f}MB")

                audio_cache[cache_id] = {
                    'query': query,
                    'filepath': cached_path,
                    'title': title,
                    'timestamp': time.time()
                }
                return cached_path, cache_id

            raise yt_dlp.utils.DownloadError("Arquivo mp3 não foi criado")

        except yt_dlp.utils.DownloadError as e:
            last_error = str(e)
            print(f"⚠️  Tentativa {i} falhou: {last_error[:200]}")
            _cleanup_partial_files(cache_id)
            if _valid_cached_audio(cached_path):
                print("✅ Áudio íntegro já estava no cache após a falha; usando-o.")
                return cached_path, cache_id
            low = last_error.lower()
            if 'sign in to confirm' in low or 'age' in low:
                print("   💡 Vídeo com restrição: configure YT_COOKIES_FILE ou YT_COOKIES_BROWSER")
            time.sleep(1)
        except Exception as e:
            last_error = str(e)
            print(f"⚠️  Tentativa {i} erro inesperado: {last_error[:200]}")
            _cleanup_partial_files(cache_id)
            if _valid_cached_audio(cached_path):
                print("✅ Áudio íntegro já estava no cache após a falha; usando-o.")
                return cached_path, cache_id

    # Último recurso: o arquivo pode ter sido criado por outra tentativa ou
    # por outra requisicao antes de um erro de rename no Windows.
    if _valid_cached_audio(cached_path):
        print("✅ Áudio íntegro encontrado no cache; retornando sem novo download.")
        return cached_path, cache_id

    print(f"❌ Todas as tentativas falharam. Último erro: {last_error}")
    print("   💡 Atualize o yt-dlp:  python -m pip install -U yt-dlp")
    print("   💡 Instale o Deno:     winget install DenoLand.Deno (e reabra o terminal)")
    print("   💡 Ou use cookies:     export YT_COOKIES_BROWSER=chrome")
    return None, None


def detect_note_duration(y, sr, onset_time, max_duration=2.0):
    """Detecta a duração de uma nota baseado na energia do sinal"""
    onset_frame = librosa.time_to_frames(onset_time, sr=sr)
    max_frames = int(max_duration * sr / 512)
    
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    
    start_idx = onset_frame
    end_idx = min(start_idx + max_frames, len(rms))
    
    if start_idx >= len(rms):
        return 0.1
    
    initial_energy = rms[start_idx]
    threshold = initial_energy * 0.3
    
    duration_frames = 1
    for i in range(start_idx + 1, end_idx):
        if rms[i] < threshold:
            break
        duration_frames += 1
    
    duration = librosa.frames_to_time(duration_frames, sr=sr)
    return float(max(0.1, min(duration, max_duration)))


def analyze_audio(file_path, difficulty='medium'):
    """Analisa o arquivo de áudio e extrai informações para o jogo"""
    try:
        print(f"Carregando áudio: {file_path}")
        y, sr = librosa.load(file_path, sr=22050)
        duration = float(librosa.get_duration(y=y, sr=sr))
        
        print(f"Duração: {duration:.2f}s, Sample rate: {sr}")
        
        tempo_result, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo_result.item()) if hasattr(tempo_result, 'item') else float(tempo_result)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        print(f"BPM detectado: {tempo:.2f}, Beats encontrados: {len(beat_times)}")
        
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True, units='frames')
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        
        print(f"Onsets detectados: {len(onset_times)}")
        
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        
        print(f"Analisando durações de notas...")
        
        notes = generate_notes_with_duration(
            y, sr, beat_times, onset_times, 
            spectral_centroids, chroma, difficulty, duration
        )
        
        audio_info = {
            'duration': duration,
            'tempo': tempo,
            'beats_count': int(len(beat_times)),
            'onsets_count': int(len(onset_times)),
            'notes_count': int(len(notes)),
            'hold_notes_count': int(sum(1 for n in notes if n.get('duration', 0) > 0.3)),
            'difficulty': difficulty,
            'sample_rate': int(sr)
        }
        
        return {
            'success': True,
            'audio_info': audio_info,
            'notes': notes
        }
        
    except Exception as e:
        print(f"Erro na análise: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def _extend_note_grid(times, total_duration, min_time_gap, start_margin=1.0, end_margin=2.0):
    """Completa a grade de tempos nas bordas e nos vazios longos da musica.

    O detector de batidas do librosa nao encontra beats em trechos sem
    percussao (introducao instrumental, final em fade). Sem isso a chart podia
    ficar 10s ou mais sem nenhuma nota no comeco ou no fim da musica. Aqui
    extrapolamos a grade usando o intervalo mediano dos tempos detectados.

    Args:
        times: tempos (segundos) ja filtrados pela dificuldade
        total_duration: duracao total do audio
        min_time_gap: intervalo minimo entre notas da dificuldade
        start_margin: primeiro instante que pode receber nota
        end_margin: segundos finais que ficam sem nota (fim da musica)

    Returns:
        Lista de tempos ordenada cobrindo as bordas da musica (com passo
        proximo de ``interval``), sem notas nos ``end_margin`` segundos finais.
    """
    start_limit = float(start_margin)
    end_limit = float(total_duration - end_margin)
    grid = sorted(float(t) for t in times)
    if end_limit <= start_limit:
        return grid

    if len(grid) >= 2:
        gaps = [b - a for a, b in zip(grid, grid[1:]) if b - a > 0]
        interval = float(np.median(gaps)) if gaps else float(min_time_gap)
    else:
        interval = float(min_time_gap)

    # Nunca menor que o gap minimo da dificuldade e nunca grande o bastante
    # para deixar buracos visiveis na chart.
    interval = min(max(interval, float(min_time_gap)), 2.0)
    max_gap = max(interval * 2.0, float(min_time_gap) * 2.0)

    # 1) Preenche vazios internos maiores que max_gap.
    if grid:
        filled = [grid[0]]
        for time in grid[1:]:
            previous = filled[-1]
            gap = time - previous
            if gap > max_gap:
                steps = int(gap / interval)
                for k in range(1, steps + 1):
                    candidate = previous + k * interval
                    if time - candidate >= min_time_gap:
                        filled.append(candidate)
            filled.append(time)
        grid = filled
    else:
        # Nenhum beat detectado: usa uma grade regular.
        grid = [start_limit]
        while grid[-1] + interval <= end_limit:
            grid.append(grid[-1] + interval)

    # 2) Estende para tras ate o inicio da musica.
    while grid[0] - interval >= start_limit:
        grid.insert(0, grid[0] - interval)

    # 3) Estende para frente ate o fim da musica.
    while grid[-1] + interval <= end_limit:
        grid.append(grid[-1] + interval)

    return grid


def generate_notes_with_duration(y, sr, beat_times, onset_times, spectral_centroids, chroma, difficulty, total_duration):
    """Gera notas do jogo COM DURAÇÃO"""
    notes = []
    note_id = 0
    
    difficulty_config = {
        'easy': {
            'use_beats': True,
            'use_onsets': False,
            'density': 0.7,
            'lanes': 3,
            'hold_probability': 0.12,
            'min_hold_duration': 0.5,
            'min_time_gap': 0.4
        },
        'medium': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.6,
            'lanes': 4,
            'hold_probability': 0.25,
            'min_hold_duration': 0.35,
            'min_time_gap': 0.25
        },
        'hard': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.75,
            'lanes': 5,
            'hold_probability': 0.3,
            'min_hold_duration': 0.3,
            'min_time_gap': 0.2
        },
        'expert': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.9,
            'lanes': 5,
            'hold_probability': 0.35,
            'min_hold_duration': 0.25,
            'min_time_gap': 0.15
        }
    }
    
    config = difficulty_config.get(difficulty, difficulty_config['medium'])
    num_lanes = config['lanes']
    min_time_gap = config['min_time_gap']
    
    all_times = []
    if config['use_beats']:
        all_times.extend(beat_times)
    if config['use_onsets']:
        all_times.extend(onset_times)
    
    all_times = sorted(list(set([round(float(t), 3) for t in all_times])))
    
    filtered_times = []
    last_time = -999
    for time in all_times:
        if time - last_time >= min_time_gap:
            filtered_times.append(time)
            last_time = time
    
    step = max(1, int(1 / config['density']))
    selected_times = filtered_times[::step]

    # Intro/outro sem percussao nao geram beats: completa a grade para a
    # chart nao comecar/terminar com longos trechos mudos.
    before_extension = len(selected_times)
    selected_times = _extend_note_grid(selected_times, total_duration, min_time_gap)

    print(f"Gerando notas - Tempos totais: {len(all_times)}, Filtrados: {len(filtered_times)}, Selecionados: {before_extension} (+{len(selected_times) - before_extension} nas bordas/vazios)")
    
    lane_counts = [0] * num_lanes
    
    for i, time in enumerate(selected_times):
        if time < 1.0:
            continue
        if time > total_duration - 2.0:
            break
        
        chroma_index = int((time / total_duration) * chroma.shape[1])
        chroma_index = min(chroma_index, chroma.shape[1] - 1)
        
        chroma_frame = chroma[:, chroma_index]
        top_pitches = np.argsort(chroma_frame)[-3:]
        
        dominant_pitch = top_pitches[-1]
        lane = dominant_pitch % num_lanes
        
        if lane_counts[lane] > np.mean(lane_counts) + 2:
            lane = int(np.argmin(lane_counts))
        
        spectral_index = int((time / total_duration) * len(spectral_centroids))
        spectral_index = min(spectral_index, len(spectral_centroids) - 1)
        normalized_centroid = spectral_centroids[spectral_index] / np.max(spectral_centroids)
        
        if np.random.random() < 0.3:
            lane = int(normalized_centroid * (num_lanes - 1))
        
        lane = max(0, min(lane, num_lanes - 1))
        lane_counts[lane] += 1
        
        is_hold_note = np.random.random() < config['hold_probability']
        
        note_duration = 0.0
        note_type = 'tap'
        
        if is_hold_note:
            note_duration = detect_note_duration(y, sr, time, max_duration=2.5)
            if note_duration >= config['min_hold_duration']:
                note_type = 'hold'
            else:
                note_duration = 0.0
                note_type = 'tap'
        
        note = {
            'id': note_id,
            'time': round(float(time), 3),
            'lane': int(lane),
            'type': note_type,
            'duration': round(float(note_duration), 3) if note_type == 'hold' else 0.0
        }
        
        notes.append(note)
        note_id += 1
    
    hold_count = sum(1 for n in notes if n['type'] == 'hold')
    print(f"Notas geradas: {len(notes)} total ({hold_count} hold notes)")
    print(f"Distribuição por lane: {lane_counts}")
    if notes:
        print(f"Cobertura: primeira nota {notes[0]['time']:.2f}s, última {notes[-1]['time']:.2f}s de {total_duration:.2f}s")
    
    return notes


# ============================================================
# NOVOS ENDPOINTS v3 - SPOTIFY + YOUTUBE
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Verifica status da API"""
    return jsonify({
        'status': 'online',
        'message': 'Guitar Hero Backend v3 - Spotify + YouTube!',
        'version': '3.0',
        'spotify_enabled': SPOTIFY_ENABLED
    })


@app.route('/search/spotify', methods=['GET'])
def search_spotify():
    """
    Busca músicas no Spotify
    
    Query params:
        q: termo de busca
        limit: número de resultados (padrão: 10)
    
    Returns:
        JSON com lista de músicas do Spotify
    """
    if not SPOTIFY_ENABLED:
        return jsonify({
            'success': False,
            'error': 'Spotify não configurado. Configure as credenciais no backend.'
        }), 503
    
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Parâmetro "q" é obrigatório'
        }), 400
    
    try:
        print(f"🔍 Buscando no Spotify: {query}")
        results = sp.search(q=query, limit=limit, type='track')
        
        tracks = []
        for item in results['tracks']['items']:
            track = {
                'id': item['id'],
                'name': item['name'],
                'artist': ', '.join([artist['name'] for artist in item['artists']]),
                'album': item['album']['name'],
                'image': item['album']['images'][0]['url'] if item['album']['images'] else None,
                'preview_url': item['preview_url'],  # 30 segundos de preview
                'duration_ms': item['duration_ms'],
                'spotify_url': item['external_urls']['spotify']
            }
            tracks.append(track)
        
        print(f"✅ Encontradas {len(tracks)} músicas")
        
        return jsonify({
            'success': True,
            'tracks': tracks
        })
        
    except Exception as e:
        print(f"❌ Erro ao buscar no Spotify: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/analyze/youtube', methods=['POST'])
def analyze_from_youtube():
    """
    Baixa música do YouTube e analisa
    AGORA RETORNA O CACHE_ID PARA STREAMING
    
    Body JSON:
        query: string de busca (ex: "Queen - Bohemian Rhapsody")
        difficulty: easy/medium/hard/expert
    
    Returns:
        JSON com notas geradas + cache_id para streaming
    """
    data = request.get_json()
    
    if not data or 'query' not in data:
        return jsonify({
            'success': False,
            'error': 'Campo "query" é obrigatório'
        }), 400
    
    query = data['query']
    difficulty = data.get('difficulty', 'medium')
    
    try:
        # Baixa do YouTube (com cache)
        filepath, cache_id = search_youtube_and_download(query, use_cache=True)
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'error': 'Falha ao baixar áudio do YouTube. Vídeo pode ter restrições.'
            }), 500
        
        # Analisa o áudio
        result = analyze_audio(filepath, difficulty)
        
        # NÃO remove o arquivo - mantém em cache!
        
        if result['success']:
            # Adiciona cache_id e URL de streaming à resposta
            result['cache_id'] = cache_id
            result['audio_url'] = f'/stream/{cache_id}'
            print(f"✅ Análise completa! Stream URL: /stream/{cache_id}")
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/stream/<cache_id>', methods=['GET'])
def stream_audio(cache_id):
    """
    Serve o arquivo de áudio para streaming
    
    Path param:
        cache_id: ID do áudio no cache
    
    Returns:
        Arquivo MP3 para streaming
    """
    try:
        # Verifica se o cache_id existe
        if cache_id in audio_cache:
            filepath = audio_cache[cache_id]['filepath']
        else:
            # Tenta encontrar o arquivo diretamente
            filepath = os.path.join(AUDIO_CACHE_FOLDER, f"{cache_id}.mp3")
        
        if not os.path.exists(filepath):
            print(f"❌ Arquivo não encontrado: {cache_id}")
            return jsonify({
                'success': False,
                'error': 'Áudio não encontrado. Cache expirado?'
            }), 404
        
        print(f"🎵 Servindo áudio: {cache_id}")
        
        # Serve o arquivo com suporte a range requests (para seek)
        return send_file(
            filepath,
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name='audio.mp3'
        )
        
    except Exception as e:
        print(f"❌ Erro ao servir áudio: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/analyze', methods=['POST'])
def analyze():
    """Endpoint original - upload de arquivo"""
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'Nenhum arquivo foi enviado'
        }), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'Nome de arquivo inválido'
        }), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': f'Extensão não permitida. Use: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400
    
    difficulty = request.form.get('difficulty', 'medium').lower()
    if difficulty not in ['easy', 'medium', 'hard', 'expert']:
        difficulty = 'medium'
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"Arquivo salvo em: {filepath}")
        
        result = analyze_audio(filepath, difficulty)
        
        try:
            os.remove(filepath)
            print(f"Arquivo temporário removido: {filepath}")
        except:
            pass
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("🎸 Guitar Hero Backend v3 - Spotify + YouTube!")
    print("=" * 60)
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Spotify Status: {'✅ Conectado' if SPOTIFY_ENABLED else '⚠️  Não configurado'}")
    print("=" * 60)
    print("\nNovos endpoints v3:")
    print("  GET  /search/spotify?q=QUERY - Busca no Spotify")
    print("  POST /analyze/youtube - Baixa do YouTube e analisa")
    print("  POST /analyze - Upload de arquivo (método antigo)")
    print("\nIniciando servidor...")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
