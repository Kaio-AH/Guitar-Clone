import React, { useState, useEffect, useRef } from 'react';
import { Music, Upload, Play, Pause, RotateCcw, Zap, AlertCircle, Loader, Flame } from 'lucide-react';

const GuitarHeroGame = () => {
  const [audioFile, setAudioFile] = useState(null);
  const [audioFileName, setAudioFileName] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [score, setScore] = useState(0);
  const [combo, setCombo] = useState(0);
  const [maxCombo, setMaxCombo] = useState(0);
  const [notes, setNotes] = useState([]);
  const [pressedKeys, setPressedKeys] = useState(new Set());
  const [holdingKeys, setHoldingKeys] = useState(new Map());
  const [difficulty, setDifficulty] = useState('medium');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [audioInfo, setAudioInfo] = useState(null);
  const [accuracy, setAccuracy] = useState(100);
  const [notesHit, setNotesHit] = useState(0);
  const [notesMissed, setNotesMissed] = useState(0);
  const [multiplier, setMultiplier] = useState(1);
  
  const audioRef = useRef(null);
  const animationRef = useRef(null);
  const notesRef = useRef([]);
  const fileInputRef = useRef(null);
  const isTogglingRef = useRef(false);

  // Configurações - CORES GUITARFLASH
  const LANES = ['A', 'S', 'D', 'F', 'J'];
  const COLORS = ['#22c55e', '#ef4444', '#eab308', '#3b82f6', '#f97316'];
  const NOTE_SPEED = 350;
  const HIT_ZONE = 60;
  const SPAWN_HEIGHT = -100;
  const TARGET_Y = 520;
  const BACKEND_URL = 'http://localhost:5000';

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
    setMultiplier(1);

    try {
      const audioUrl = URL.createObjectURL(file);
      setAudioFile(audioUrl);

      const formData = new FormData();
      formData.append('file', file);
      formData.append('difficulty', difficulty);

      console.log(`📤 Enviando arquivo (${difficulty})...`);

      const response = await fetch(`${BACKEND_URL}/analyze`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`Erro: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        console.log(`✅ ${data.notes.length} notas (${data.audio_info.hold_notes_count} hold)`);
        
        const preparedNotes = data.notes.map(note => ({
          ...note,
          y: SPAWN_HEIGHT,
          hit: false,
          missed: false,
          holding: false,
          holdProgress: 0
        }));

        setNotes(preparedNotes);
        notesRef.current = preparedNotes;
        setAudioInfo(data.audio_info);
        
        if (audioRef.current && audioUrl) {
          audioRef.current.src = audioUrl;
          audioRef.current.preload = 'auto';
          audioRef.current.load();
        }
        
        setIsAnalyzing(false);
      } else {
        throw new Error(data.error || 'Erro desconhecido');
      }

    } catch (error) {
      console.error('❌ Erro:', error);
      setAnalysisError(`${error.message}. Backend rodando?`);
      setIsAnalyzing(false);
      setAudioFile(null);
    }
  };

  useEffect(() => {
    if (audioFile && audioRef.current && notes.length > 0 && !audioRef.current.src) {
      audioRef.current.src = audioFile;
      audioRef.current.preload = 'auto';
      audioRef.current.load();
    }
  }, [audioFile, notes]);

  useEffect(() => {
    if (!isPlaying || !audioRef.current) return;

    let lastTime = 0;
    
    const animate = (timestamp) => {
      if (timestamp - lastTime < 16) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }
      lastTime = timestamp;
      
      const currentTime = audioRef.current.currentTime;
      
      setNotes(prevNotes => {
        return prevNotes.map(note => {
          if (note.hit || note.missed) return note;
          
          const timeDiff = currentTime - note.time;
          const newY = TARGET_Y + (timeDiff * NOTE_SPEED);
          
          if (note.type === 'hold' && note.holding) {
            const endTime = note.time + note.duration;
            const holdProgress = Math.min(1, (currentTime - note.time) / note.duration);
            
            if (currentTime >= endTime) {
              return { ...note, hit: true, holdProgress: 1 };
            }
            
            return { ...note, y: newY, holdProgress };
          }
          
          if (newY > TARGET_Y + HIT_ZONE && !note.missed && !note.hit && !note.holding) {
            setCombo(0);
            setMultiplier(1);
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

  useEffect(() => {
    if (combo >= 50) setMultiplier(4);
    else if (combo >= 30) setMultiplier(3);
    else if (combo >= 10) setMultiplier(2);
    else setMultiplier(1);
  }, [combo]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      const key = e.key.toUpperCase();
      if (!LANES.includes(key)) return;
      
      if (!pressedKeys.has(key)) {
        setPressedKeys(prev => new Set([...prev, key]));
        if (isPlaying) checkHit(key, 'down');
      }
    };

    const handleKeyUp = (e) => {
      const key = e.key.toUpperCase();
      if (!LANES.includes(key)) return;
      
      setPressedKeys(prev => {
        const newSet = new Set(prev);
        newSet.delete(key);
        return newSet;
      });
      
      if (isPlaying) checkHit(key, 'up');
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [pressedKeys, isPlaying]);

  const checkHit = (key, action) => {
    const laneIndex = LANES.indexOf(key);
    if (laneIndex === -1) return;

    setNotes(prevNotes => {
      let hitDetected = false;
      
      const updatedNotes = prevNotes.map(note => {
        if (hitDetected) return note;
        if (note.lane !== laneIndex) return note;
        if (note.hit || note.missed) return note;
        
        const distance = Math.abs(note.y - TARGET_Y);
        
        if (action === 'down' && distance < HIT_ZONE) {
          hitDetected = true;
          
          if (note.type === 'tap') {
            const precision = 1 - (distance / HIT_ZONE);
            let pointMultiplier = 1;
            
            if (precision > 0.9) pointMultiplier = 2;
            else if (precision > 0.7) pointMultiplier = 1.5;
            else if (precision > 0.5) pointMultiplier = 1.2;
            
            const points = Math.floor(100 * pointMultiplier * multiplier);
            
            setScore(prev => prev + points);
            setCombo(prev => {
              const newCombo = prev + 1;
              setMaxCombo(current => Math.max(current, newCombo));
              return newCombo;
            });
            setNotesHit(prev => prev + 1);
            
            return { ...note, hit: true };
            
          } else if (note.type === 'hold') {
            console.log('🎹 Hold iniciada!');
            setHoldingKeys(prev => new Map(prev).set(key, note.id));
            return { ...note, holding: true };
          }
        }
        
        if (action === 'up' && note.type === 'hold' && note.holding) {
          hitDetected = true;
          
          const currentTime = audioRef.current?.currentTime || 0;
          const holdTime = currentTime - note.time;
          const holdPercentage = Math.min(1, holdTime / note.duration);
          
          const holdPoints = Math.floor(200 * holdPercentage * multiplier);
          
          setScore(prev => prev + holdPoints);
          
          if (holdPercentage >= 0.9) {
            setCombo(prev => {
              const newCombo = prev + 2;
              setMaxCombo(current => Math.max(current, newCombo));
              return newCombo;
            });
            setNotesHit(prev => prev + 1);
          } else if (holdPercentage >= 0.5) {
            setCombo(prev => prev + 1);
            setNotesHit(prev => prev + 1);
          } else {
            setCombo(0);
            setMultiplier(1);
          }
          
          setHoldingKeys(prev => {
            const newMap = new Map(prev);
            newMap.delete(key);
            return newMap;
          });
          
          return { ...note, hit: true, holdProgress: holdPercentage };
        }
        
        return note;
      });
      
      return updatedNotes;
    });
  };

  const togglePlay = () => {
    if (isTogglingRef.current || !audioRef.current || notes.length === 0) return;

    isTogglingRef.current = true;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
      isTogglingRef.current = false;
    } else {
      const playPromise = audioRef.current.play();
      
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            setIsPlaying(true);
            isTogglingRef.current = false;
          })
          .catch(err => {
            console.error('❌', err);
            setAnalysisError('Erro ao tocar');
            isTogglingRef.current = false;
          });
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
    setMultiplier(1);
    setHoldingKeys(new Map());
    
    if (notes.length > 0) {
      const resetNotes = notesRef.current.map(note => ({
        ...note,
        y: SPAWN_HEIGHT,
        hit: false,
        missed: false,
        holding: false,
        holdProgress: 0
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

  const getActiveLanes = () => {
    const lanes = { easy: 3, medium: 4, hard: 5, expert: 5 };
    return lanes[difficulty] || 5;
  };

  const activeLanes = getActiveLanes();
  const displayLanes = LANES.slice(0, activeLanes);
  const displayColors = COLORS.slice(0, activeLanes);

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-950 via-gray-900 to-black text-white">
      <div className="p-6 bg-black bg-opacity-70 backdrop-blur-sm border-b border-purple-500">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <Music className="w-8 h-8 text-purple-400" />
              <div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-green-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                  Guitar Hero v2
                </h1>
                <p className="text-xs text-gray-400 mt-1">Com Hold Notes! 🎸</p>
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
                  <div className="text-2xl font-bold text-pink-400 flex items-center gap-1">
                    {combo}x
                    {multiplier > 1 && <span className="text-sm text-orange-400">({multiplier}x)</span>}
                  </div>
                </div>
              </div>
            )}
          </div>

          {audioInfo && (
            <div className="mt-4 p-3 bg-gradient-to-r from-purple-900/30 to-pink-900/30 rounded-lg border border-purple-500/30 flex justify-between items-center">
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
                  <span className="text-gray-400">Notas:</span>
                  <span className="ml-2 font-semibold">{audioInfo.notes_count}</span>
                  <span className="ml-1 text-xs text-green-400">({audioInfo.hold_notes_count} hold)</span>
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
                      <div className="text-gray-400">Detectando hold notes</div>
                    </div>
                  </>
                ) : (
                  <>
                    <Upload className="w-20 h-20 text-purple-400" />
                    <div className="text-center">
                      <div className="text-2xl font-semibold mb-2">Upload uma música</div>
                      <div className="text-sm text-gray-400">MP3, WAV, OGG, FLAC, M4A</div>
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

            <div className="mt-8">
              <div className="text-center mb-4">
                <div className="text-sm text-gray-400 mb-2">Selecione a dificuldade</div>
              </div>
              <div className="grid grid-cols-4 gap-3">
                {['easy', 'medium', 'hard', 'expert'].map(level => (
                  <button
                    key={level}
                    onClick={() => setDifficulty(level)}
                    disabled={isAnalyzing}
                    className={`py-3 px-4 rounded-lg font-semibold uppercase text-sm transition-all ${
                      difficulty === level
                        ? 'bg-purple-600 text-white shadow-lg'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                    } ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>

            {analysisError && (
              <div className="mt-6 p-4 bg-red-900 bg-opacity-50 border border-red-500 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-red-200">{analysisError}</div>
              </div>
            )}

            <div className="mt-8 p-6 bg-gradient-to-br from-purple-900/20 to-pink-900/20 rounded-lg border border-purple-500/30">
              <h3 className="text-lg font-semibold mb-3 text-purple-300">🎮 Novidades v2</h3>
              <ul className="text-sm text-gray-300 space-y-2">
                <li>• <strong>Hold Notes</strong> - Segure as teclas!</li>
                <li>• <strong>Cores GuitarFlash</strong> - Verde, Vermelho, Amarelo, Azul, Laranja</li>
                <li>• <strong>Multiplicador 4x</strong> - Combo aumenta pontos</li>
                <li>• <strong>Detecção automática</strong> de notas sustentadas</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {audioFile && notes.length > 0 && (
        <div className="relative max-w-7xl mx-auto mt-8 px-6 pb-12">
          <div className="flex justify-center gap-4 mb-8">
            <button
              onClick={togglePlay}
              className="flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-lg font-semibold transition-all shadow-lg"
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
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-pink-600 to-purple-600 rounded-lg font-semibold transition-all"
            >
              <Upload className="w-5 h-5" />
              Nova
            </button>
          </div>

          <div className="grid grid-cols-5 gap-4 mb-6">
            <div className="bg-gradient-to-br from-green-900/30 to-green-800/30 p-4 rounded-lg text-center border border-green-500/30">
              <div className="text-xs text-gray-400 mb-1">Acertos</div>
              <div className="text-2xl font-bold text-green-400">{notesHit}</div>
            </div>
            <div className="bg-gradient-to-br from-red-900/30 to-red-800/30 p-4 rounded-lg text-center border border-red-500/30">
              <div className="text-xs text-gray-400 mb-1">Erros</div>
              <div className="text-2xl font-bold text-red-400">{notesMissed}</div>
            </div>
            <div className="bg-gradient-to-br from-orange-900/30 to-orange-800/30 p-4 rounded-lg text-center border border-orange-500/30">
              <div className="text-xs text-gray-400 mb-1">Max Combo</div>
              <div className="text-2xl font-bold text-orange-400">{maxCombo}x</div>
            </div>
            <div className="bg-gradient-to-br from-purple-900/30 to-purple-800/30 p-4 rounded-lg text-center border border-purple-500/30">
              <div className="text-xs text-gray-400 mb-1">Multiplicador</div>
              <div className="text-2xl font-bold text-purple-400 flex items-center justify-center gap-1">
                {multiplier}x
                {multiplier >= 4 && <Flame className="w-5 h-5 text-orange-500" />}
              </div>
            </div>
            <div className="bg-gradient-to-br from-blue-900/30 to-blue-800/30 p-4 rounded-lg text-center border border-blue-500/30">
              <div className="text-xs text-gray-400 mb-1">Total</div>
              <div className="text-2xl font-bold text-blue-400">{notes.length}</div>
            </div>
          </div>

          <div className="relative h-[600px] bg-gradient-to-b from-gray-900 to-black rounded-xl overflow-hidden border-4 border-purple-500 shadow-2xl">
            <div className="absolute inset-0 flex">
              {displayLanes.map((lane, index) => (
                <div
                  key={lane}
                  className="flex-1 border-r-2 border-gray-800 last:border-r-0 relative transition-all duration-100"
                  style={{
                    backgroundColor: pressedKeys.has(lane) ? `${displayColors[index]}30` : 'transparent'
                  }}
                >
                  <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-b from-gray-700 to-transparent opacity-50" />
                </div>
              ))}
            </div>

            <div 
              className="absolute inset-x-0 h-24 border-y-4 border-yellow-400 bg-yellow-400 bg-opacity-10 z-10"
              style={{ top: `${TARGET_Y - HIT_ZONE/2}px` }}
            >
              <div className="flex h-full">
                {displayLanes.map((lane, index) => (
                  <div key={lane} className="flex-1 flex items-center justify-center border-r border-yellow-400 last:border-r-0">
                    <div 
                      className={`text-5xl font-bold transition-all duration-100 ${
                        pressedKeys.has(lane) ? 'scale-125 text-white' : 'text-gray-700'
                      }`}
                    >
                      {lane}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {notes.map(note => {
              if (note.hit || note.missed) return null;
              if (note.y < SPAWN_HEIGHT || note.y > 650) return null;
              if (note.lane >= activeLanes) return null;

              const noteColor = displayColors[note.lane];
              const laneWidth = 100 / activeLanes;
              const laneLeft = (note.lane / activeLanes) * 100;

              return (
                <div key={note.id}>
                  {/* CAUDA DA HOLD NOTE - MUITO MAIS VISÍVEL */}
                  {note.type === 'hold' && (
                    <div
                      className="absolute"
                      style={{
                        top: `${note.y + 56}px`, // Começa logo abaixo da bolinha
                        left: `${laneLeft}%`,
                        width: `${laneWidth}%`,
                        height: `${note.duration * NOTE_SPEED}px`,
                        zIndex: 4
                      }}
                    >
                      <div 
                        className="mx-4 relative"
                        style={{
                          height: '100%',
                          background: note.holding 
                            ? `linear-gradient(to bottom, ${noteColor}FF, ${noteColor}CC, ${noteColor}99)` 
                            : `linear-gradient(to bottom, ${noteColor}DD, ${noteColor}AA, ${noteColor}77)`,
                          border: `4px solid ${noteColor}`,
                          borderRadius: '8px',
                          boxShadow: note.holding 
                            ? `0 0 40px ${noteColor}, inset 0 0 30px ${noteColor}80`
                            : `0 0 20px ${noteColor}80, inset 0 0 20px ${noteColor}40`,
                          opacity: note.holding ? 1 : 0.9
                        }}
                      >
                        {/* Listras internas para dar textura */}
                        <div className="absolute inset-0 flex flex-col justify-around opacity-30">
                          {[...Array(Math.max(3, Math.floor(note.duration * 3)))].map((_, i) => (
                            <div 
                              key={i} 
                              className="h-1 bg-white"
                              style={{ marginLeft: '2px', marginRight: '2px' }}
                            />
                          ))}
                        </div>
                        
                        {/* Barra de progresso para hold notes sendo seguradas */}
                        {note.holding && note.holdProgress > 0 && (
                          <div 
                            className="absolute inset-0 bg-white opacity-30"
                            style={{
                              height: `${note.holdProgress * 100}%`,
                              transition: 'height 0.05s linear'
                            }}
                          />
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* BOLINHA DA NOTA (CÍRCULO GUITARFLASH STYLE) */}
                  <div
                    className="absolute flex items-center justify-center"
                    style={{
                      top: `${note.y}px`,
                      left: `${laneLeft}%`,
                      width: `${laneWidth}%`,
                      height: '56px',
                      zIndex: 5
                    }}
                  >
                    <div 
                      className="relative"
                      style={{
                        width: '80%',
                        height: '56px',
                        maxWidth: '70px'
                      }}
                    >
                      {/* Círculo principal */}
                      <div
                        className="absolute inset-0 rounded-full"
                        style={{
                          backgroundColor: noteColor,
                          boxShadow: `
                            0 0 40px ${noteColor}, 
                            0 0 20px ${noteColor},
                            0 4px 15px rgba(0,0,0,0.5),
                            inset 0 -8px 15px rgba(0,0,0,0.3),
                            inset 0 8px 15px rgba(255,255,255,0.3)
                          `,
                          border: '4px solid white',
                          transform: pressedKeys.has(displayLanes[note.lane]) ? 'scale(0.9)' : 'scale(1)',
                          transition: 'transform 0.1s'
                        }}
                      />
                      
                      {/* Brilho interno */}
                      <div
                        className="absolute rounded-full"
                        style={{
                          top: '15%',
                          left: '20%',
                          width: '40%',
                          height: '30%',
                          background: 'radial-gradient(circle, rgba(255,255,255,0.8) 0%, rgba(255,255,255,0) 70%)',
                          filter: 'blur(3px)'
                        }}
                      />
                      
                      {/* Indicador de hold note no centro */}
                      {note.type === 'hold' && (
                        <div className="absolute inset-0 flex items-center justify-center">
                          <div 
                            className="w-6 h-6 rounded-full border-4 border-white"
                            style={{
                              backgroundColor: note.holding ? 'white' : 'transparent',
                              boxShadow: note.holding ? '0 0 10px white' : 'none'
                            }}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {!isPlaying && (
              <div className="absolute inset-0 bg-black bg-opacity-70 flex items-center justify-center z-20">
                <div className="text-center">
                  <Play className="w-20 h-20 mx-auto mb-4 text-purple-400" />
                  <div className="text-2xl font-bold">Clique em Jogar!</div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 text-center text-gray-400">
            <p className="text-lg">
              Use <span className="font-bold text-white">{displayLanes.join(' ')}</span> para tocar
            </p>
            <p className="text-sm mt-2">
              Segure as teclas para hold notes! 🎹
            </p>
          </div>
        </div>
      )}

      <audio 
        ref={audioRef} 
        onEnded={() => {
          setIsPlaying(false);
          console.log('🏁 Fim!');
        }}
      />
    </div>
  );
};

export default GuitarHeroGame;