import React, { useState, useEffect, useRef } from 'react';
import { Music, Upload, Play, Pause, RotateCcw, Zap, AlertCircle, Loader } from 'lucide-react';

const GuitarHeroGame = () => {
  const [audioFile, setAudioFile] = useState(null);
  const [audioFileName, setAudioFileName] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [score, setScore] = useState(0);
  const [combo, setCombo] = useState(0);
  const [maxCombo, setMaxCombo] = useState(0);
  const [notes, setNotes] = useState([]);
  const [pressedKeys, setPressedKeys] = useState(new Set());
  const [difficulty, setDifficulty] = useState('medium');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [audioInfo, setAudioInfo] = useState(null);
  const [accuracy, setAccuracy] = useState(100);
  const [notesHit, setNotesHit] = useState(0);
  const [notesMissed, setNotesMissed] = useState(0);
  
  const audioRef = useRef(null);
  const animationRef = useRef(null);
  const notesRef = useRef([]);
  const fileInputRef = useRef(null);
  const isTogglingRef = useRef(false);

  // Configurações do jogo
  const LANES = ['A', 'S', 'D', 'F', 'J'];
  const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6'];
  const NOTE_SPEED = 350;
  const HIT_ZONE = 60;
  const SPAWN_HEIGHT = -100;
  const TARGET_Y = 520;
  const BACKEND_URL = 'http://localhost:5000';

  // Handler para upload de arquivo
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('audio/')) {
      setAnalysisError('Por favor, selecione um arquivo de áudio válido');
      return;
    }

    setAudioFileName(file.name);
    setAnalysisError(null);
    setIsAnalyzing(true);
    setScore(0);
    setCombo(0);
    setMaxCombo(0);
    setNotesHit(0);
    setNotesMissed(0);
    setAccuracy(100);

    try {
      // Cria URL local para o áudio
      const audioUrl = URL.createObjectURL(file);
      setAudioFile(audioUrl);

      // Envia para o backend para análise
      const formData = new FormData();
      formData.append('file', file);
      formData.append('difficulty', difficulty);

      console.log(`Enviando arquivo para análise (dificuldade: ${difficulty})...`);

      const response = await fetch(`${BACKEND_URL}/analyze`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`Erro na análise: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        console.log(`✅ Análise completa! ${data.notes.length} notas geradas`);
        console.log(`🎵 BPM: ${data.audio_info.tempo.toFixed(2)}`);
        
        // Prepara as notas com posição inicial
        const preparedNotes = data.notes.map(note => ({
          ...note,
          y: SPAWN_HEIGHT,
          hit: false,
          missed: false
        }));

        setNotes(preparedNotes);
        notesRef.current = preparedNotes;
        setAudioInfo(data.audio_info);
        
        // Configura o áudio IMEDIATAMENTE após análise
        if (audioRef.current && audioUrl) {
          console.log('🎵 Configurando áudio com URL:', audioUrl);
          audioRef.current.src = audioUrl;
          audioRef.current.preload = 'auto';
          audioRef.current.load();
        }
        
        setIsAnalyzing(false);
      } else {
        throw new Error(data.error || 'Erro desconhecido na análise');
      }

    } catch (error) {
      console.error('Erro ao processar arquivo:', error);
      setAnalysisError(`Erro: ${error.message}. Certifique-se que o backend está rodando em ${BACKEND_URL}`);
      setIsAnalyzing(false);
      setAudioFile(null);
    }
  };

  // Inicializa o áudio - BACKUP caso não tenha sido configurado
  useEffect(() => {
    if (audioFile && audioRef.current && notes.length > 0 && !audioRef.current.src) {
      console.log('🔄 Configurando áudio via useEffect...');
      console.log('URL do áudio:', audioFile);
      
      audioRef.current.src = audioFile;
      audioRef.current.preload = 'auto';
      audioRef.current.load();
    }

    // Event listeners
    if (audioRef.current) {
      const handleLoaded = () => {
        console.log('✅ Áudio pronto! Duration:', audioRef.current.duration);
        console.log('ReadyState:', audioRef.current.readyState);
      };
      
      const handleError = (e) => {
        console.error('❌ Erro ao carregar áudio:', e);
        console.error('Error code:', audioRef.current.error);
      };

      const handleCanPlay = () => {
        console.log('✅ Can play! ReadyState:', audioRef.current.readyState);
      };
      
      audioRef.current.addEventListener('loadeddata', handleLoaded);
      audioRef.current.addEventListener('canplay', handleCanPlay);
      audioRef.current.addEventListener('error', handleError);
      
      return () => {
        if (audioRef.current) {
          audioRef.current.removeEventListener('loadeddata', handleLoaded);
          audioRef.current.removeEventListener('canplay', handleCanPlay);
          audioRef.current.removeEventListener('error', handleError);
        }
      };
    }
  }, [audioFile, notes]);

  // Sistema de animação das notas - CORRIGIDO
  useEffect(() => {
    if (!isPlaying || !audioRef.current) {
      return;
    }

    let lastTime = 0;
    
    const animate = (timestamp) => {
      // Limita a taxa de atualização para ~60 FPS
      if (timestamp - lastTime < 16) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }
      lastTime = timestamp;
      
      const currentTime = audioRef.current.currentTime;
      
      setNotes(prevNotes => {
        return prevNotes.map(note => {
          if (note.hit || note.missed) return note;
          
          // Calcula posição Y baseada no tempo real da música
          const timeDiff = currentTime - note.time;
          const newY = TARGET_Y + (timeDiff * NOTE_SPEED);
          
          // Verifica se a nota passou da zona de acerto
          if (newY > TARGET_Y + HIT_ZONE && !note.missed && !note.hit) {
            setCombo(0);
            setNotesMissed(prev => prev + 1);
            return { ...note, y: newY, missed: true };
          }
          
          return { ...note, y: newY };
        });
      });
      
      animationRef.current = requestAnimationFrame(animate);
    };
    
    animationRef.current = requestAnimationFrame(animate);
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying]);

  // Atualiza precisão
  const updateAccuracy = (hits, misses) => {
    const total = hits + misses;
    if (total > 0) {
      setAccuracy(Math.round((hits / total) * 100));
    }
  };

  // Sistema de detecção de teclas
  useEffect(() => {
    const handleKeyDown = (e) => {
      const key = e.key.toUpperCase();
      if (LANES.includes(key) && !pressedKeys.has(key)) {
        setPressedKeys(prev => new Set([...prev, key]));
        if (isPlaying) {
          checkHit(key);
        }
      }
    };

    const handleKeyUp = (e) => {
      const key = e.key.toUpperCase();
      setPressedKeys(prev => {
        const newSet = new Set(prev);
        newSet.delete(key);
        return newSet;
      });
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [pressedKeys, isPlaying]);

  // Verifica se acertou alguma nota
  const checkHit = (key) => {
    const laneIndex = LANES.indexOf(key);
    if (laneIndex === -1) return;

    setNotes(prevNotes => {
      let hitDetected = false;
      const updatedNotes = prevNotes.map(note => {
        if (note.lane === laneIndex && 
            !note.hit && 
            !note.missed && 
            !hitDetected &&
            Math.abs(note.y - TARGET_Y) < HIT_ZONE) {
          hitDetected = true;
          
          // Calcula pontos baseado na precisão
          const distance = Math.abs(note.y - TARGET_Y);
          const precision = 1 - (distance / HIT_ZONE);
          let multiplier = 1;
          let rating = 'OK';
          
          if (precision > 0.9) {
            multiplier = 2;
            rating = 'PERFECT!';
          } else if (precision > 0.7) {
            multiplier = 1.5;
            rating = 'GREAT!';
          } else if (precision > 0.5) {
            multiplier = 1.2;
            rating = 'GOOD';
          }
          
          const basePoints = 100;
          const comboBonus = 1 + (combo * 0.1);
          const points = Math.floor(basePoints * multiplier * comboBonus);
          
          setScore(prev => prev + points);
          setCombo(prev => {
            const newCombo = prev + 1;
            setMaxCombo(current => Math.max(current, newCombo));
            return newCombo;
          });
          setNotesHit(prev => {
            const newHits = prev + 1;
            updateAccuracy(newHits, notesMissed);
            return newHits;
          });
          
          console.log(`${rating} +${points} pontos`);
          
          return { ...note, hit: true };
        }
        return note;
      });
      
      return updatedNotes;
    });
  };

  // Controles de playback - COM TIMEOUT
  const togglePlay = () => {
    // Previne cliques múltiplos
    if (isTogglingRef.current) {
      console.log('⚠️ Aguarde...');
      return;
    }

    if (!audioRef.current || notes.length === 0) {
      console.error('❌ Não é possível tocar');
      return;
    }

    isTogglingRef.current = true;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
      console.log('⏸️ Pausado');
      isTogglingRef.current = false;
    } else {
      console.log('▶️ Iniciando reprodução...');
      console.log('Audio src:', audioRef.current.src);
      console.log('ReadyState:', audioRef.current.readyState);
      console.log('Duration:', audioRef.current.duration);
      
      // Timeout de segurança (5 segundos)
      const timeout = setTimeout(() => {
        console.error('⏱️ Timeout! Forçando liberação...');
        isTogglingRef.current = false;
        setAnalysisError('Timeout ao iniciar áudio. Tente novamente.');
      }, 5000);
      
      const playPromise = audioRef.current.play();
      
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            clearTimeout(timeout);
            setIsPlaying(true);
            console.log('✅ Tocando!');
            isTogglingRef.current = false;
          })
          .catch(err => {
            clearTimeout(timeout);
            console.error('❌ Erro:', err);
            console.error('Tipo de erro:', err.name);
            
            if (err.name === 'NotAllowedError') {
              setAnalysisError('Permissão negada. Clique novamente.');
            } else if (err.name === 'NotSupportedError') {
              setAnalysisError('Formato de áudio não suportado.');
            } else {
              setAnalysisError('Erro ao tocar. Tente recarregar a página.');
            }
            
            isTogglingRef.current = false;
          });
      } else {
        clearTimeout(timeout);
        isTogglingRef.current = false;
      }
    }
  };

  const resetGame = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsPlaying(false);
    setScore(0);
    setCombo(0);
    setMaxCombo(0);
    setNotesHit(0);
    setNotesMissed(0);
    setAccuracy(100);
    
    if (audioInfo && notes.length > 0) {
      // Reseta as notas para o estado inicial
      const resetNotes = notesRef.current.map(note => ({
        ...note,
        y: SPAWN_HEIGHT,
        hit: false,
        missed: false
      }));
      setNotes(resetNotes);
    }
  };

  const newSong = () => {
    resetGame();
    setAudioFile(null);
    setAudioFileName('');
    setNotes([]);
    setAudioInfo(null);
    setAnalysisError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Mudança de dificuldade
  const handleDifficultyChange = (newDifficulty) => {
    setDifficulty(newDifficulty);
  };

  // Calcula estatísticas do jogo
  const getActiveLanes = () => {
    const difficultyLanes = {
      'easy': 3,
      'medium': 4,
      'hard': 5,
      'expert': 5
    };
    return difficultyLanes[difficulty] || 5;
  };

  const activeLanes = getActiveLanes();
  const displayLanes = LANES.slice(0, activeLanes);
  const displayColors = COLORS.slice(0, activeLanes);

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-purple-900 to-black text-white">
      {/* Header */}
      <div className="p-6 bg-black bg-opacity-50 backdrop-blur-sm border-b border-purple-500">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <Music className="w-8 h-8 text-purple-400" />
              <div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                  Guitar Hero AI
                </h1>
                <p className="text-xs text-gray-400 mt-1">Powered by Librosa + Python</p>
              </div>
            </div>
            
            {audioFile && (
              <div className="flex items-center gap-6">
                <div className="text-right">
                  <div className="text-xs text-gray-400">Score</div>
                  <div className="text-2xl font-bold text-yellow-400">{score.toLocaleString()}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-400">Combo</div>
                  <div className="text-2xl font-bold text-pink-400">{combo}x</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-400">Precisão</div>
                  <div className="text-2xl font-bold text-green-400">{accuracy}%</div>
                </div>
              </div>
            )}
          </div>

          {/* Informações da música */}
          {audioInfo && (
            <div className="mt-4 p-3 bg-gray-800 bg-opacity-50 rounded-lg flex justify-between items-center">
              <div className="flex items-center gap-6 text-sm">
                <div>
                  <span className="text-gray-400">Música:</span>
                  <span className="ml-2 font-semibold text-purple-300">{audioFileName}</span>
                </div>
                <div>
                  <span className="text-gray-400">BPM:</span>
                  <span className="ml-2 font-semibold">{audioInfo.tempo.toFixed(0)}</span>
                </div>
                <div>
                  <span className="text-gray-400">Duração:</span>
                  <span className="ml-2 font-semibold">{Math.floor(audioInfo.duration / 60)}:{(audioInfo.duration % 60).toFixed(0).padStart(2, '0')}</span>
                </div>
                <div>
                  <span className="text-gray-400">Notas:</span>
                  <span className="ml-2 font-semibold">{audioInfo.notes_count}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-yellow-400" />
                <span className="text-xs font-semibold uppercase text-yellow-400">{difficulty}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Área de upload */}
      {!audioFile && (
        <div className="flex items-center justify-center min-h-[70vh] p-6">
          <div className="max-w-2xl w-full">
            <label className="cursor-pointer block">
              <div className="flex flex-col items-center gap-6 p-16 border-4 border-dashed border-purple-500 rounded-2xl hover:border-pink-500 transition-all bg-black bg-opacity-30 hover:bg-opacity-50">
                {isAnalyzing ? (
                  <>
                    <Loader className="w-20 h-20 text-purple-400 animate-spin" />
                    <div className="text-center">
                      <div className="text-2xl font-semibold mb-2">Analisando música...</div>
                      <div className="text-gray-400">Detectando BPM, beats e gerando notas</div>
                    </div>
                  </>
                ) : (
                  <>
                    <Upload className="w-20 h-20 text-purple-400" />
                    <div className="text-center">
                      <div className="text-2xl font-semibold mb-2">Upload uma música</div>
                      <div className="text-sm text-gray-400">MP3, WAV, OGG, FLAC, M4A</div>
                      <div className="text-xs text-gray-500 mt-2">Máximo 50MB</div>
                    </div>
                  </>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                onChange={handleFileUpload}
                disabled={isAnalyzing}
                className="hidden"
              />
            </label>

            {/* Seletor de dificuldade */}
            <div className="mt-8">
              <div className="text-center mb-4">
                <div className="text-sm text-gray-400 mb-2">Selecione a dificuldade</div>
              </div>
              <div className="grid grid-cols-4 gap-3">
                {['easy', 'medium', 'hard', 'expert'].map(level => (
                  <button
                    key={level}
                    onClick={() => handleDifficultyChange(level)}
                    disabled={isAnalyzing}
                    className={`py-3 px-4 rounded-lg font-semibold uppercase text-sm transition-all ${
                      difficulty === level
                        ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/50'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                    } ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>

            {/* Erro */}
            {analysisError && (
              <div className="mt-6 p-4 bg-red-900 bg-opacity-50 border border-red-500 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-red-200">{analysisError}</div>
              </div>
            )}

            {/* Instruções */}
            <div className="mt-8 p-6 bg-gray-800 bg-opacity-30 rounded-lg">
              <h3 className="text-lg font-semibold mb-3 text-purple-300">ℹ️ Como funciona</h3>
              <ul className="text-sm text-gray-300 space-y-2">
                <li>• O backend Python analisa sua música usando Librosa</li>
                <li>• Detecta BPM, beats e onsets automaticamente</li>
                <li>• Gera notas sincronizadas com a música</li>
                <li>• Quanto maior a dificuldade, mais notas aparecem</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Área do jogo */}
      {audioFile && notes.length > 0 && (
        <div className="relative max-w-7xl mx-auto mt-8 px-6 pb-12">
          {/* Controles */}
          <div className="flex justify-center gap-4 mb-8">
            <button
              onClick={togglePlay}
              disabled={isTogglingRef.current}
              className="flex items-center gap-2 px-8 py-3 bg-purple-600 hover:bg-purple-700 rounded-lg font-semibold transition-colors shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
              {isPlaying ? 'Pausar' : 'Jogar'}
            </button>
            <button
              onClick={resetGame}
              className="flex items-center gap-2 px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold transition-colors"
            >
              <RotateCcw className="w-5 h-5" />
              Reiniciar
            </button>
            <button
              onClick={newSong}
              className="flex items-center gap-2 px-6 py-3 bg-pink-600 hover:bg-pink-700 rounded-lg font-semibold transition-colors"
            >
              <Upload className="w-5 h-5" />
              Nova Música
            </button>
          </div>

          {/* Estatísticas */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-gray-800 bg-opacity-50 p-4 rounded-lg text-center">
              <div className="text-xs text-gray-400 mb-1">Acertos</div>
              <div className="text-2xl font-bold text-green-400">{notesHit}</div>
            </div>
            <div className="bg-gray-800 bg-opacity-50 p-4 rounded-lg text-center">
              <div className="text-xs text-gray-400 mb-1">Erros</div>
              <div className="text-2xl font-bold text-red-400">{notesMissed}</div>
            </div>
            <div className="bg-gray-800 bg-opacity-50 p-4 rounded-lg text-center">
              <div className="text-xs text-gray-400 mb-1">Max Combo</div>
              <div className="text-2xl font-bold text-orange-400">{maxCombo}x</div>
            </div>
            <div className="bg-gray-800 bg-opacity-50 p-4 rounded-lg text-center">
              <div className="text-xs text-gray-400 mb-1">Total Notas</div>
              <div className="text-2xl font-bold text-blue-400">{notes.length}</div>
            </div>
          </div>

          {/* Canvas do jogo */}
          <div className="relative h-[600px] bg-black bg-opacity-50 rounded-xl overflow-hidden border-4 border-purple-500 shadow-2xl">
            {/* Lanes */}
            <div className="absolute inset-0 flex">
              {displayLanes.map((lane, index) => (
                <div
                  key={lane}
                  className="flex-1 border-r border-gray-700 last:border-r-0 relative transition-all duration-100"
                  style={{
                    backgroundColor: pressedKeys.has(lane) 
                      ? `${displayColors[index]}30` 
                      : 'transparent'
                  }}
                >
                  {/* Linhas guia */}
                  <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-b from-gray-600 to-transparent opacity-30" />
                  <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-t from-gray-600 to-transparent opacity-30" />
                </div>
              ))}
            </div>

            {/* Zona de acerto */}
            <div 
              className="absolute inset-x-0 h-24 border-y-4 border-yellow-400 bg-yellow-400 bg-opacity-10 z-10"
              style={{ top: `${TARGET_Y - HIT_ZONE/2}px` }}
            >
              <div className="flex h-full">
                {displayLanes.map((lane, index) => (
                  <div key={lane} className="flex-1 flex items-center justify-center border-r border-yellow-400 last:border-r-0">
                    <div 
                      className={`text-5xl font-bold transition-all duration-100 ${
                        pressedKeys.has(lane) ? 'scale-125 text-white' : 'text-gray-600'
                      }`}
                    >
                      {lane}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Notas */}
            {notes.map(note => (
              !note.hit && !note.missed && note.y > SPAWN_HEIGHT && note.y < 650 && note.lane < activeLanes && (
                <div
                  key={note.id}
                  className="absolute transition-opacity duration-150"
                  style={{
                    top: `${note.y}px`,
                    left: `${(note.lane / activeLanes) * 100}%`,
                    width: `${100 / activeLanes}%`,
                    opacity: note.hit ? 0 : 1,
                    zIndex: 5
                  }}
                >
                  <div 
                    className="mx-2 h-14 rounded-lg shadow-lg border-2 border-white border-opacity-30"
                    style={{
                      backgroundColor: displayColors[note.lane],
                      boxShadow: `0 0 25px ${displayColors[note.lane]}`
                    }}
                  />
                </div>
              )
            ))}

            {/* Overlay quando pausado */}
            {!isPlaying && (
              <div className="absolute inset-0 bg-black bg-opacity-70 flex items-center justify-center z-20">
                <div className="text-center">
                  <Play className="w-20 h-20 mx-auto mb-4 text-purple-400" />
                  <div className="text-2xl font-bold">Clique em Jogar para começar</div>
                </div>
              </div>
            )}
          </div>

          {/* Instruções */}
          <div className="mt-6 text-center text-gray-400">
            <p className="text-lg">
              Use as teclas{' '}
              <span className="font-bold text-white">
                {displayLanes.join(' ')}
              </span>
              {' '}para tocar as notas
            </p>
            <p className="text-sm mt-2">
              Pressione quando as notas chegarem na zona amarela! Quanto mais preciso, mais pontos!
            </p>
          </div>
        </div>
      )}

      {/* Áudio invisível */}
      <audio 
        ref={audioRef} 
        onEnded={() => {
          setIsPlaying(false);
          console.log('🏁 Música finalizada!');
        }}
      />
    </div>
  );
};

export default GuitarHeroGame;