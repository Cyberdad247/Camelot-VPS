import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, MessageSquare, Mic, MicOff, Radio, Send, Sparkles, Volume2, VolumeX } from 'lucide-react';
import './throne-room-knight-council.css';

export interface ThroneKnight {
  id: string;
  name: string;
  title: string;
  engine: string;
  sge: string;
  vram: string;
  quote: string;
  directives: string[];
  color: string;
  icon: string;
}

interface ThroneRoomKnightCouncilProps {
  knights: ThroneKnight[];
  selectedKnight: ThroneKnight;
  onSelectKnight: (knight: ThroneKnight) => void;
  decree: string;
  onDecreeChange: (value: string) => void;
  response: string | null;
  onSend: (message?: string) => void;
  soundEnabled?: boolean;
}

type SpeechRecognitionCtor = new () => {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: any) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

const armorStrip = 'https://raw.githubusercontent.com/Cyberdad247/Multivoice-router/main/public/armor-strip.png';
const throneHall = 'https://raw.githubusercontent.com/Cyberdad247/Multivoice-router/main/public/hall.png';

const wrap = (value: number, count: number) => ((value % count) + count) % count;

export const ThroneRoomKnightCouncil: React.FC<ThroneRoomKnightCouncilProps> = ({
  knights,
  selectedKnight,
  onSelectKnight,
  decree,
  onDecreeChange,
  response,
  onSend,
  soundEnabled = true,
}) => {
  const selectedIndex = Math.max(0, knights.findIndex(knight => knight.id === selectedKnight.id));
  const [mode, setMode] = useState<'2d' | '3d'>('3d');
  const [awake, setAwake] = useState(true);
  const [autoRotate, setAutoRotate] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [liveHud, setLiveHud] = useState(true);
  const [transcript, setTranscript] = useState<{ speaker: string; text: string }[]>([
    { speaker: 'THRONE ROOM', text: 'Council link established. Select a Knight and speak your intent.' },
  ]);
  const recognitionRef = useRef<InstanceType<SpeechRecognitionCtor> | null>(null);

  const active = knights[selectedIndex] ?? knights[0];
  const count = knights.length;

  const knightViews = useMemo(() => knights.map((knight, index) => {
    let offset = index - selectedIndex;
    if (offset > count / 2) offset -= count;
    if (offset < -count / 2) offset += count;
    return { knight, index, offset };
  }), [count, knights, selectedIndex]);

  const selectByDelta = (delta: number) => {
    if (!count) return;
    const next = knights[wrap(selectedIndex + delta, count)];
    if (next) onSelectKnight(next);
    setAutoRotate(false);
  };

  useEffect(() => {
    if (!autoRotate || count < 2) return;
    const timer = window.setInterval(() => {
      const next = knights[wrap(selectedIndex + 1, count)];
      if (next) onSelectKnight(next);
    }, 3600);
    return () => window.clearInterval(timer);
  }, [autoRotate, count, knights, onSelectKnight, selectedIndex]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest('input,textarea,button')) return;
      if (event.key === 'ArrowLeft') selectByDelta(-1);
      if (event.key === 'ArrowRight') selectByDelta(1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const stopVoice = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    setIsSpeaking(false);
  };

  const previewVoice = () => {
    if (isSpeaking) {
      stopVoice();
      return;
    }
    if (!('speechSynthesis' in window)) return;
    const utterance = new SpeechSynthesisUtterance(`I am ${active.name}. ${active.quote}`);
    utterance.rate = 0.9;
    utterance.pitch = 0.95;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
  };

  const startListening = () => {
    const win = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionCtor;
      webkitSpeechRecognition?: SpeechRecognitionCtor;
    };
    const Recognition = win.SpeechRecognition ?? win.webkitSpeechRecognition;
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = event => {
      const text = event.results?.[0]?.[0]?.transcript?.trim();
      if (text) onDecreeChange(text);
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();
  };

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }
    startListening();
  };

  const submit = () => {
    const text = decree.trim();
    if (!text) return;
    setTranscript(previous => [...previous.slice(-7), { speaker: 'YOU', text }]);
    onSend(text);
  };

  useEffect(() => {
    if (!response) return;
    setTranscript(previous => [...previous.slice(-7), { speaker: active.name.toUpperCase(), text: response }]);
  }, [active.name, response]);

  return (
    <div className={`throne-voice-council ${mode === '2d' ? 'flat' : ''} ${awake ? 'awakened' : ''}`} style={{ ['--knight-accent' as string]: active.color }}>
      <div className="throne-hall-bg" style={{ backgroundImage: `linear-gradient(rgba(3,4,7,.45),rgba(3,4,7,.92)),url(${throneHall})` }} />

      <header className="throne-council-header">
        <div>
          <span className="throne-eyebrow">TEN PERSONAS. ONE COUNCIL.</span>
          <h3>Choose your <em>knight.</em></h3>
          <p>The Throne Room is Camelot's conversational chamber. Select a Knight, awaken the link, then speak or type your intent.</p>
        </div>
        <div className="throne-view-controls" role="group" aria-label="Council view controls">
          <button className={mode === '2d' ? 'active' : ''} onClick={() => setMode('2d')}>2D</button>
          <button className={mode === '3d' ? 'active' : ''} onClick={() => setMode('3d')}>3D</button>
          <button className={autoRotate ? 'active' : ''} onClick={() => setAutoRotate(value => !value)}>Orbit</button>
          <button className={liveHud ? 'active' : ''} onClick={() => setLiveHud(value => !value)}><MessageSquare size={13}/> Live HUD</button>
        </div>
      </header>

      <div className="throne-carousel-shell" aria-label="Knight voice selector">
        <button className="throne-arrow left" onClick={() => selectByDelta(-1)} aria-label="Previous knight"><ChevronLeft/></button>
        <div className="throne-carousel-stage">
          {knightViews.map(({ knight, index, offset }) => {
            const distance = Math.abs(offset);
            const visible = distance <= 3;
            const selected = offset === 0;
            return (
              <button
                key={knight.id}
                className={`throne-knight-card ${selected ? 'selected' : ''}`}
                style={{
                  ['--offset' as string]: offset,
                  ['--distance' as string]: distance,
                  ['--accent' as string]: knight.color,
                  opacity: visible ? Math.max(.18, 1 - distance * .22) : 0,
                  pointerEvents: visible ? 'auto' : 'none',
                }}
                onClick={() => onSelectKnight(knight)}
                aria-pressed={selected}
              >
                <div className="throne-armor-window">
                  <div
                    className="throne-armor-sprite"
                    style={{
                      backgroundImage: `url(${armorStrip})`,
                      backgroundPosition: `${(index % 7) * (100 / 6)}% center`,
                    }}
                  />
                  <div className="throne-armor-light" />
                </div>
                <div className="throne-knight-meta">
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <strong>{knight.name}</strong>
                  <small>{knight.title}</small>
                </div>
              </button>
            );
          })}
        </div>
        <button className="throne-arrow right" onClick={() => selectByDelta(1)} aria-label="Next knight"><ChevronRight/></button>
      </div>

      <div className="throne-conversation-grid">
        <section className="throne-active-knight">
          <div className="throne-active-heading"><Sparkles size={15}/><span>ACTIVE KNIGHT</span><b>{awake ? 'AWAKE' : 'DORMANT'}</b></div>
          <div className="throne-active-identity">
            <div className="throne-active-icon">{active.icon}</div>
            <div><strong>{active.name}</strong><span>{active.title}</span><small>{active.engine}</small></div>
          </div>
          <blockquote>“{active.quote}”</blockquote>
          <div className="throne-directives">{active.directives.map(item => <span key={item}>{item}</span>)}</div>
          <div className="throne-knight-stats"><span>SGE <b>{active.sge}</b></span><span>VRAM <b>{active.vram}</b></span><span>VOICE LINK <b>{soundEnabled ? 'READY' : 'MUTED'}</b></span></div>
          <div className="throne-active-actions">
            <button className={awake ? 'active' : ''} onClick={() => setAwake(value => !value)}><Radio size={14}/>{awake ? 'Armor Awakened' : 'Awaken Armor'}</button>
            <button onClick={previewVoice}>{isSpeaking ? <VolumeX size={14}/> : <Volume2 size={14}/>} {isSpeaking ? 'Stop Voice' : 'Preview Voice'}</button>
          </div>
        </section>

        <section className="throne-dialogue">
          <div className="throne-dialogue-heading"><MessageSquare size={15}/><span>LIVE COUNCIL CHANNEL</span><b>{active.name}</b></div>
          {liveHud && (
            <div className="throne-transcript" role="log" aria-live="polite">
              {transcript.map((item, index) => <div key={`${item.speaker}-${index}`} className={item.speaker === 'YOU' ? 'user' : ''}><span>{item.speaker}</span><p>{item.text}</p></div>)}
            </div>
          )}
          <div className="throne-compose">
            <button className={`throne-mic ${isListening ? 'listening' : ''}`} onClick={toggleListening} title="Voice input when browser speech recognition is available">
              {isListening ? <MicOff size={18}/> : <Mic size={18}/>}<span>{isListening ? 'Listening' : 'Speak'}</span>
            </button>
            <textarea
              value={decree}
              onChange={event => onDecreeChange(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
              rows={3}
              placeholder={`Speak to ${active.name}...`}
            />
            <button className="throne-send" onClick={submit}><Send size={16}/><span>Send to Knight</span></button>
          </div>
          <div className="throne-channel-note">Text and local browser speech controls are live. Remote synthesized conversation remains governed by the Multivoice/Bifrost integration boundary.</div>
        </section>
      </div>
    </div>
  );
};

export default ThroneRoomKnightCouncil;
