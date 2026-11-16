import React, { useState, useEffect, useRef } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';
import { Mic, MicOff, Volume2, Sparkles, Package, ShoppingBag, CreditCard, RefreshCw, ShieldAlert } from 'lucide-react';

const GET_TOKEN_BASE_URL = 'http://localhost:8000/api/token';

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [agentState, setAgentState] = useState('Disconnected');
  const [transcripts, setTranscripts] = useState([
    { sender: 'Aria', text: 'Hello! I am Aria, your AI customer support assistant for India. Click "Start Voice Conversation" or any query template below to begin.', type: 'agent' }
  ]);
  
  const roomRef = useRef(null);
  const audioElRef = useRef(null);

  useEffect(() => {
    return () => {
      cleanupRoom();
    };
  }, []);

  const cleanupRoom = () => {
    if (roomRef.current) {
      try {
        roomRef.current.removeAllListeners();
        roomRef.current.disconnect();
      } catch (e) {
        console.warn('Error during room disconnect:', e);
      }
      roomRef.current = null;
    }
  };

  const connectToRoom = async () => {
    cleanupRoom();
    setIsConnecting(true);
    setAgentState('Connecting...');

    try {
      const sessionRoomName = `ecommerce-support-room-${Date.now()}`;
      const sessionParticipant = `Customer-${Math.floor(Math.random() * 1000)}`;

      const res = await fetch(`${GET_TOKEN_BASE_URL}?room_name=${encodeURIComponent(sessionRoomName)}&participant_name=${encodeURIComponent(sessionParticipant)}`);
      if (!res.ok) {
        throw new Error('Failed to fetch authentication token from backend server');
      }
      const data = await res.json();

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        publishDefaults: {
          simulcast: false,
        },
      });

      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
          const element = track.attach();
          document.body.appendChild(element);
          element.play().catch(e => console.warn('Audio play notice:', e));
          setAgentState('Speaking');
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach().forEach((el) => el.remove());
      });

      room.on(RoomEvent.DataReceived, (payload, participant) => {
        const strData = new TextDecoder().decode(payload);
        try {
          const parsed = JSON.parse(strData);
          if (parsed.text) {
            if (parsed.sender === 'You' || parsed.type === 'user' || parsed.sender === 'User') {
              setTranscripts(prev => {
                const last = prev[prev.length - 1];
                if (last && last.type === 'user' && last.text === parsed.text) return prev;
                return [...prev, { sender: 'You', text: parsed.text, type: 'user' }];
              });
            } else if (parsed.sender === 'Aria' || parsed.type === 'agent') {
              setTranscripts(prev => {
                const last = prev[prev.length - 1];
                if (last && last.type === 'agent' && last.text === parsed.text) return prev;
                return [...prev, { sender: 'Aria', text: parsed.text, type: 'agent' }];
              });
            }
          }
        } catch (e) {
          console.log('Received raw data string:', strData);
        }
      });

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        if (speakers.some(s => s.isAgent)) {
          setAgentState('Speaking');
        } else if (speakers.some(s => !s.isAgent)) {
          setAgentState('Listening');
        } else {
          setAgentState('Connected');
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        setIsConnected(false);
        setIsConnecting(false);
        setAgentState('Disconnected');
        cleanupRoom();
      });

      await room.connect(data.server_url, data.token);

      try {
        await room.startAudio();
      } catch (audioErr) {
        console.warn('Audio unlock notice:', audioErr);
      }

      for (const p of room.remoteParticipants.values()) {
        for (const pub of p.trackPublications.values()) {
          if (pub.track && pub.track.kind === Track.Kind.Audio) {
            const element = pub.track.attach();
            document.body.appendChild(element);
            setAgentState('Speaking');
          }
        }
      }

      const enableMicWithRetry = async (retries = 3) => {
        for (let i = 0; i < retries; i++) {
          try {
            if (typeof room.localParticipant.setMicrophoneEnabled === 'function') {
              await room.localParticipant.setMicrophoneEnabled(true);
            } else if (typeof room.localParticipant.enableMicrophone === 'function') {
              await room.localParticipant.enableMicrophone();
            }
            return true;
          } catch (micErr) {
            console.warn(`Microphone publish attempt ${i + 1} waiting for engine:`, micErr);
            if (i < retries - 1) {
              await new Promise((resolve) => setTimeout(resolve, 800));
            }
          }
        }
        return false;
      };

      await enableMicWithRetry();

      setIsConnected(true);
      setIsConnecting(false);
      setAgentState('Listening');

      setTranscripts(prev => [...prev, { sender: 'System', text: 'Connected to LiveKit Room. Aria is online and listening...', type: 'system' }]);
      return room;

    } catch (err) {
      console.error('Connection error:', err);
      alert(`Could not connect to LiveKit: ${err.message}. Please verify backend/server.py and agent.py are running.`);
      setIsConnecting(false);
      setAgentState('Disconnected');
      cleanupRoom();
      return null;
    }
  };

  const handleConnectToggle = async () => {
    if (isConnected || isConnecting) {
      cleanupRoom();
      setIsConnected(false);
      setIsConnecting(false);
      setAgentState('Disconnected');
      setTranscripts(prev => [...prev, { sender: 'System', text: 'Call ended.', type: 'system' }]);
    } else {
      await connectToRoom();
    }
  };

  const sendQueryToAgent = async (activeRoom, promptText) => {
    if (activeRoom && activeRoom.state === 'connected') {
      try {
        const payload = new TextEncoder().encode(JSON.stringify({ text: promptText, sender: 'User' }));
        await activeRoom.localParticipant.publishData(payload, { reliable: true });
      } catch (err) {
        console.error('Error publishing chip query prompt:', err);
      }
    }
  };

  const handleChipClick = async (promptText) => {
    setTranscripts(prev => [...prev, { sender: 'You', text: promptText, type: 'user' }]);
    
    let activeRoom = roomRef.current;
    if (!isConnected || !activeRoom || activeRoom.state !== 'connected') {
      activeRoom = await connectToRoom();
    }
    
    if (activeRoom) {
      setTimeout(() => {
        sendQueryToAgent(activeRoom, promptText);
      }, 600);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand-title">
          <Sparkles className="w-6 h-6 text-indigo-400" />
          <h1>Aria Voice Assistant</h1>
          <span className="badge">Indian E-Commerce Edition</span>
        </div>
        <div className="status-pill">
          <span className={`status-dot ${isConnected ? 'connected' : ''} ${agentState.toLowerCase()}`}></span>
          <span>{agentState}</span>
        </div>
      </header>

      <main className="voice-stage">
        <div className={`orb-container ${agentState.toLowerCase()}`}>
          {isConnected ? <Volume2 className="orb-icon" /> : <MicOff className="orb-icon" />}
        </div>

        <button 
          className={`action-btn ${isConnected ? 'stop' : 'start'}`}
          onClick={handleConnectToggle}
          disabled={isConnecting}
        >
          {isConnecting ? (
            <span>Connecting...</span>
          ) : isConnected ? (
            <>
              <MicOff size={20} />
              <span>End Call</span>
            </>
          ) : (
            <>
              <Mic size={20} />
              <span>Start Voice Conversation</span>
            </>
          )}
        </button>

        <div className="chips-container">
          <button className="chip" onClick={() => handleChipClick("Can you check the status of my recent order?")}>
            <Package size={14} style={{ display: 'inline', marginRight: 6 }} />
            Check Order Status
          </button>
          <button className="chip" onClick={() => handleChipClick("Can you check the price and stock availability of a product?")}>
            <ShoppingBag size={14} style={{ display: 'inline', marginRight: 6 }} />
            Product Price & Stock (₹)
          </button>
          <button className="chip" onClick={() => handleChipClick("What payment methods, UPI apps, and Cash on Delivery options do you accept?")}>
            <CreditCard size={14} style={{ display: 'inline', marginRight: 6 }} />
            UPI & Payment Methods
          </button>
          <button className="chip" onClick={() => handleChipClick("What is your 10-day return and refund policy?")}>
            <RefreshCw size={14} style={{ display: 'inline', marginRight: 6 }} />
            Returns & Refund FAQ
          </button>
          <button className="chip" onClick={() => handleChipClick("Can you change my shipping address or contact phone number?")}>
            <ShieldAlert size={14} style={{ display: 'inline', marginRight: 6 }} />
            Customer Support Help (Out of Scope)
          </button>
        </div>
      </main>

      <section className="transcript-section">
        <div className="transcript-title">Live Conversation Transcript</div>
        <div className="transcript-log">
          {transcripts.map((t, idx) => (
            <div key={idx} className={`chat-bubble ${t.type || 'agent'}`}>
              <strong>{t.sender}: </strong> {t.text}
            </div>
          ))}
        </div>
      </section>

      <audio ref={audioElRef} autoPlay />
    </div>
  );
}
