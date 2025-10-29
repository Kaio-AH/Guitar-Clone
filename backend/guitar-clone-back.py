"""
Guitar Hero Backend - v2
Sistema de análise de áudio com NOTAS LONGAS (hold notes)
Estilo GuitarFlash

Requisitos:
pip install flask flask-cors librosa numpy soundfile

Uso:
python guitar_hero_backend.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import librosa
import numpy as np
import os
import json
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
CORS(app)

# Configurações
UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac', 'm4a'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


def allowed_file(filename):
    """Verifica se o arquivo tem uma extensão permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def detect_note_duration(y, sr, onset_time, max_duration=2.0):
    """
    Detecta a duração de uma nota baseado na energia do sinal
    
    Args:
        y: sinal de áudio
        sr: sample rate
        onset_time: tempo de início da nota
        max_duration: duração máxima a verificar
    
    Returns:
        duração da nota em segundos
    """
    # Converte tempo para frame
    onset_frame = librosa.time_to_frames(onset_time, sr=sr)
    max_frames = int(max_duration * sr / 512)  # hop_length padrão = 512
    
    # Calcula RMS (energia) do sinal
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    
    # Pega a energia a partir do onset
    start_idx = onset_frame
    end_idx = min(start_idx + max_frames, len(rms))
    
    if start_idx >= len(rms):
        return 0.1  # Nota muito curta
    
    # Energia inicial da nota
    initial_energy = rms[start_idx]
    threshold = initial_energy * 0.3  # 30% da energia inicial
    
    # Procura onde a energia cai abaixo do threshold
    duration_frames = 1
    for i in range(start_idx + 1, end_idx):
        if rms[i] < threshold:
            break
        duration_frames += 1
    
    # Converte frames para tempo
    duration = librosa.frames_to_time(duration_frames, sr=sr)
    
    # Limita entre 0.1 e max_duration
    return float(max(0.1, min(duration, max_duration)))


def analyze_audio(file_path, difficulty='medium'):
    """
    Analisa o arquivo de áudio e extrai informações para o jogo
    AGORA COM NOTAS LONGAS!
    
    Args:
        file_path: caminho do arquivo de áudio
        difficulty: nível de dificuldade ('easy', 'medium', 'hard', 'expert')
    
    Returns:
        dict com informações do áudio e notas geradas
    """
    try:
        # Carrega o áudio
        print(f"Carregando áudio: {file_path}")
        y, sr = librosa.load(file_path, sr=22050)
        duration = float(librosa.get_duration(y=y, sr=sr))
        
        print(f"Duração: {duration:.2f}s, Sample rate: {sr}")
        
        # Detecta tempo e beats
        tempo_result, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo_result.item()) if hasattr(tempo_result, 'item') else float(tempo_result)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        print(f"BPM detectado: {tempo:.2f}, Beats encontrados: {len(beat_times)}")
        
        # Detecta onset (início de notas/eventos musicais)
        onset_frames = librosa.onset.onset_detect(
            y=y, 
            sr=sr, 
            backtrack=True,
            units='frames'
        )
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        
        print(f"Onsets detectados: {len(onset_times)}")
        
        # Extrai características espectrais
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        
        # Calcula chromagram para detectar notas musicais
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        
        print(f"Analisando durações de notas...")
        
        # Gera notas COM DURAÇÃO baseadas na dificuldade
        notes = generate_notes_with_duration(
            y,
            sr,
            beat_times, 
            onset_times, 
            spectral_centroids,
            chroma,
            difficulty,
            duration
        )
        
        # Informações do áudio
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


def generate_notes_with_duration(y, sr, beat_times, onset_times, spectral_centroids, chroma, difficulty, total_duration):
    """
    Gera as notas do jogo COM DURAÇÃO (hold notes)
    
    Args:
        y: sinal de áudio
        sr: sample rate
        beat_times: timestamps dos beats
        onset_times: timestamps dos onsets
        spectral_centroids: características espectrais
        chroma: informação de pitch
        difficulty: nível de dificuldade
        total_duration: duração total da música
    
    Returns:
        lista de notas para o jogo (com type: 'tap' ou 'hold')
    """
    notes = []
    note_id = 0
    
    # Configurações por dificuldade
    difficulty_config = {
        'easy': {
            'use_beats': True,
            'use_onsets': False,
            'density': 0.4,
            'lanes': 3,
            'hold_probability': 0.15,  # 15% de chance de nota longa
            'min_hold_duration': 0.3
        },
        'medium': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.65,
            'lanes': 4,
            'hold_probability': 0.25,
            'min_hold_duration': 0.3
        },
        'hard': {
            'use_beats': True,
            'use_onsets': True,
            'density': 0.8,
            'lanes': 5,
            'hold_probability': 0.35,
            'min_hold_duration': 0.25
        },
        'expert': {
            'use_beats': True,
            'use_onsets': True,
            'density': 1.0,
            'lanes': 5,
            'hold_probability': 0.45,
            'min_hold_duration': 0.2
        }
    }
    
    config = difficulty_config.get(difficulty, difficulty_config['medium'])
    num_lanes = config['lanes']
    
    # Combina beats e onsets
    all_times = []
    
    if config['use_beats']:
        all_times.extend(beat_times)
    
    if config['use_onsets']:
        all_times.extend(onset_times)
    
    # Remove duplicatas e ordena
    all_times = sorted(list(set([round(float(t), 3) for t in all_times])))
    
    # Aplica densidade
    step = max(1, int(1 / config['density']))
    selected_times = all_times[::step]
    
    print(f"Gerando notas - Tempos totais: {len(all_times)}, Selecionados: {len(selected_times)}")
    
    # Calcula RMS para detecção de duração
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    
    # Gera notas
    for i, time in enumerate(selected_times):
        if time < 1.0:  # Pula primeiro segundo
            continue
            
        if time > total_duration - 2.0:  # Pula últimos 2 segundos
            break
        
        # Determina a lane baseado no centroid espectral
        spectral_index = int((time / total_duration) * len(spectral_centroids))
        spectral_index = min(spectral_index, len(spectral_centroids) - 1)
        
        # Normaliza centroid para lane (0 a num_lanes-1)
        normalized_centroid = spectral_centroids[spectral_index] / np.max(spectral_centroids)
        lane = int(normalized_centroid * (num_lanes - 1))
        lane = max(0, min(lane, num_lanes - 1))
        
        # Decide se é nota longa ou curta
        is_hold_note = np.random.random() < config['hold_probability']
        
        note_duration = 0.0
        note_type = 'tap'
        
        if is_hold_note:
            # Detecta duração da nota
            note_duration = detect_note_duration(y, sr, time, max_duration=2.5)
            
            # Só considera hold note se duração for significativa
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
    
    return notes


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar se a API está funcionando"""
    return jsonify({
        'status': 'online',
        'message': 'Guitar Hero Backend v2 - With Hold Notes!',
        'version': '2.0'
    })


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Endpoint principal para upload e análise de áudio
    
    Parâmetros:
        file: arquivo de áudio (multipart/form-data)
        difficulty: 'easy', 'medium', 'hard', 'expert' (opcional, padrão: medium)
    
    Retorna:
        JSON com informações do áudio e notas geradas (incluindo hold notes)
    """
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
        
        # Analisa o áudio
        result = analyze_audio(filepath, difficulty)
        
        # Remove arquivo temporário
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
        print(f"Erro no endpoint /analyze: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao processar arquivo: {str(e)}'
        }), 500


@app.route('/test-generation', methods=['GET'])
def test_generation():
    """
    Endpoint de teste que gera notas sintéticas COM HOLD NOTES
    """
    duration = float(request.args.get('duration', 180))
    difficulty = request.args.get('difficulty', 'medium')
    
    bpm = 120
    beat_interval = 60 / bpm
    beat_times = np.arange(0, duration, beat_interval)
    onset_times = np.arange(0, duration, beat_interval / 2)
    
    spectral_centroids = np.random.rand(int(duration * 100)) * 5000
    
    # Gera sinal sintético para teste
    sr = 22050
    y = np.random.randn(int(duration * sr)) * 0.1
    
    chroma = np.random.rand(12, int(duration * 100))
    
    notes = generate_notes_with_duration(
        y, sr, beat_times, onset_times, 
        spectral_centroids, chroma, difficulty, duration
    )
    
    hold_count = sum(1 for n in notes if n['type'] == 'hold')
    
    return jsonify({
        'success': True,
        'audio_info': {
            'duration': duration,
            'tempo': bpm,
            'beats_count': len(beat_times),
            'onsets_count': len(onset_times),
            'notes_count': len(notes),
            'hold_notes_count': hold_count,
            'difficulty': difficulty,
            'sample_rate': sr
        },
        'notes': notes
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🎸 Guitar Hero Backend v2 - WITH HOLD NOTES!")
    print("=" * 60)
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Extensões permitidas: {', '.join(ALLOWED_EXTENSIONS)}")
    print(f"Tamanho máximo: {MAX_FILE_SIZE / (1024*1024)}MB")
    print("=" * 60)
    print("\nNovidades v2:")
    print("  ✨ Notas longas (hold notes)")
    print("  ✨ Detecção de duração automática")
    print("  ✨ Tipos: 'tap' e 'hold'")
    print("=" * 60)
    print("\nEndpoints disponíveis:")
    print("  GET  /health - Verifica status da API")
    print("  POST /analyze - Analisa arquivo de áudio")
    print("  GET  /test-generation - Gera notas de teste")
    print("\nIniciando servidor...")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)