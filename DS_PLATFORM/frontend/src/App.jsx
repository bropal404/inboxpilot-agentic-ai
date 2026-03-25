import React, { useState, useEffect, useRef } from 'react';

function App() {
  const [apps, setApps] = useState([]);
  const [selectedApp, setSelectedApp] = useState(null);
  const [userId, setUserId] = useState(`user-${Math.floor(Math.random() * 10000)}`);
  const [messages, setMessages] = useState([]);
  const [inputStr, setInputStr] = useState('');
  const [connected, setConnected] = useState(false);
  const [file, setFile] = useState(null);
  const [deploying, setDeploying] = useState(false);
  const ws = useRef(null);

  const fetchApps = () => {
    fetch('http://localhost:8000/api/apps')
      .then(res => res.json())
      .then(data => {
        setApps(data.apps);
        if (data.apps.length > 0 && !selectedApp) {
          setSelectedApp(data.apps[0].name);
        }
      })
      .catch(console.error);
  };

  useEffect(() => {
    fetchApps();
    const interval = setInterval(fetchApps, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (ws.current) {
      ws.current.close();
      setConnected(false);
    }
    setMessages([]);

    if (!selectedApp) return;

    ws.current = new WebSocket(`ws://localhost:8000/ws/chat/${selectedApp}/${userId}`);
    ws.current.onopen = () => setConnected(true);
    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'agent') {
        setMessages(prev => [...prev, { text: data.text, from: 'agent' }]);
      }
    };
    ws.current.onclose = () => setConnected(false);

    return () => {
      if (ws.current) ws.current.close();
    };
  }, [selectedApp, userId]);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const deployApp = () => {
    if (!file) {
      alert("Select a tar.gz file first!");
      return;
    }
    setDeploying(true);
    const formData = new FormData();
    formData.append("file", file);

    fetch('http://localhost:8000/api/deploy', {
      method: 'POST',
      body: formData
    })
      .then(res => res.json())
      .then(data => {
        alert(data.status + " on port " + data.port);
        fetchApps();
      })
      .catch(console.error)
      .finally(() => setDeploying(false));
  };

  const deleteSelectedApp = () => {
    if (!selectedApp) return;
    fetch(`http://localhost:8000/api/apps/${selectedApp}`, { method: 'DELETE' })
      .then(res => res.json())
      .then(data => {
        fetchApps();
        setSelectedApp(null);
        setMessages([]);
      })
      .catch(console.error);
  };

  const sendMessage = () => {
    if (!inputStr.trim() || !connected) return;
    setMessages(prev => [...prev, { text: inputStr, from: 'user' }]);
    ws.current.send(inputStr);
    setInputStr('');
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif', maxWidth: '800px', margin: 'auto' }}>
      <h1>Multi-App Platform Dashboard</h1>
      <div style={{ padding: '15px', background: '#f5f5f5', borderRadius: '5px' }}>
        <h2>App Registry</h2>
        <div style={{ marginBottom: '15px' }}>
          <input type="file" accept=".tar,.tar.gz" onChange={handleFileChange} />
          <button
            onClick={deployApp}
            disabled={deploying}
            style={{ background: '#007bff', color: 'white', padding: '10px', border: 'none', borderRadius: '5px', cursor: 'pointer', marginLeft: '10px' }}
          >
            {deploying ? "Deploying..." : "Upload & Deploy"}
          </button>
        </div>

        <ul style={{ marginTop: '10px' }}>
          {apps.map(app => (
            <li key={app.id}>
              <strong>{app.name}</strong>
              <span style={{ color: 'gray', marginLeft: '10px' }}>Port: {app.port} | Status: {app.status}</span>
            </li>
          ))}
          {apps.length === 0 && <li>No apps running.</li>}
        </ul>
      </div>

      <div style={{ marginTop: '30px', border: '1px solid #ddd', padding: '20px', borderRadius: '5px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Agent Chat</h2>
          <div>
            User ID: <input value={userId} onChange={e => setUserId(e.target.value)} style={{ width: '100px' }} />
          </div>
        </div>

        <div style={{ marginBottom: '15px', marginTop: '10px' }}>
          <label><strong>Select App:</strong> </label>
          <select value={selectedApp || ""} onChange={e => setSelectedApp(e.target.value)}>
            <option value="" disabled>-- Select an App --</option>
            {apps.map(a => <option key={a.name} value={a.name}>{a.name}</option>)}
          </select>
          {selectedApp && (
            <button onClick={deleteSelectedApp} style={{ marginLeft: '15px', background: 'red', color: 'white', border: 'none', padding: '5px', borderRadius: '5px', cursor: 'pointer' }}>
              Stop {selectedApp}
            </button>
          )}
        </div>

        <div style={{ color: connected ? 'green' : 'red', fontWeight: 'bold' }}>
          {selectedApp ? (connected ? 'WebSocket Connected' : 'WebSocket Disconnected') : 'Select an app to connect'}
        </div>

        <div style={{ background: '#fafafa', border: '1px solid #ccc', height: '300px', overflowY: 'scroll', padding: '15px', marginTop: '10px', borderRadius: '5px', opacity: selectedApp ? 1 : 0.5 }}>
          {messages.map((m, i) => (
            <div key={i} style={{ textAlign: m.from === 'user' ? 'right' : 'left', margin: '10px 0' }}>
              <span style={{
                background: m.from === 'user' ? '#007bff' : '#e0e0e0',
                color: m.from === 'user' ? '#fff' : '#000',
                padding: '8px 12px',
                borderRadius: '15px',
                display: 'inline-block',
                maxWidth: '70%',
                wordWrap: 'break-word'
              }}>
                {m.text}
              </span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: '15px', display: 'flex', gap: '10px' }}>
          <input
            value={inputStr}
            onChange={e => setInputStr(e.target.value)}
            style={{ flex: 1, padding: '10px', border: '1px solid #ccc', borderRadius: '5px' }}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder="Type a message to the agent..."
            disabled={!selectedApp}
          />
          <button
            onClick={sendMessage}
            disabled={!selectedApp}
            style={{ width: '100px', background: selectedApp ? '#28a745' : '#ccc', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
