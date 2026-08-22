/**
 * CoChem-DOCK: Stage 9.0 - Crash-Proof Telemetry & Real-Time Console Single-Page Application.
 *
 * Architecture: Zero-Build React / Tailwind CSS SPA.
 * Ecosystem Role: Out-of-band streaming console for massive quantum chemistry (ORCA, CFOUR, xTB)
 * calculation output. Implements a strictly bounded RingBuffer and IndexedDB persistence engine
 * to guard against V8 JavaScript heap Out-Of-Memory exceptions and browser DOM thrashing.
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';

// ============================================================================
// Scientific Constants & Physical Conversion Factors
// ============================================================================
export const HARTREE_TO_EV = 27.211386245988;
export const HARTREE_TO_KCAL_MOL = 627.5094740631;
export const HARTREE_TO_KJ_MOL = 2625.4996394799;
export const BOHR_TO_ANGSTROM = 0.529177210903;

export const DEFAULT_BUFFER_CAPACITY = 10000;
export const DEFAULT_THROTTLE_MS = 33; // ~30 FPS rendering target
export const DEFAULT_WS_RECONNECT_INTERVAL_MS = 1500;
export const MAX_WS_RECONNECT_INTERVAL_MS = 30000;
export const HEARTBEAT_PING_INTERVAL_MS = 15000;

// ============================================================================
// Ring Buffer Memory Safety Guard (Anti-V8 OOM)
// ============================================================================
export class RingBuffer {
  /**
   * High-throughput FIFO Ring Buffer.
   * Evicts oldest records when capacity is exceeded to prevent JavaScript heap exhaustion.
   * @param {number} capacity - Maximum number of lines to retain in RAM.
   */
  constructor(capacity = DEFAULT_BUFFER_CAPACITY) {
    this.capacity = Math.max(100, capacity);
    this.items = [];
    this.totalReceived = 0;
    this.totalDropped = 0;
  }

  setCapacity(newCapacity) {
    this.capacity = Math.max(100, newCapacity);
    if (this.items.length > this.capacity) {
      const dropCount = this.items.length - this.capacity;
      this.items.splice(0, dropCount);
      this.totalDropped += dropCount;
    }
  }

  push(item) {
    this.totalReceived += 1;
    if (this.items.length >= this.capacity) {
      this.items.shift();
      this.totalDropped += 1;
    }
    this.items.push(item);
  }

  pushBatch(itemList) {
    if (!itemList || itemList.length === 0) return;
    this.totalReceived += itemList.length;
    this.items.push(...itemList);
    if (this.items.length > this.capacity) {
      const excess = this.items.length - this.capacity;
      this.items.splice(0, excess);
      this.totalDropped += excess;
    }
  }

  getItems() {
    return this.items;
  }

  clear() {
    this.items = [];
    this.totalReceived = 0;
    this.totalDropped = 0;
  }

  get stats() {
    return {
      size: this.items.length,
      capacity: this.capacity,
      totalReceived: this.totalReceived,
      totalDropped: this.totalDropped,
      usagePercent: Math.min(100, Math.round((this.items.length / this.capacity) * 100)),
    };
  }
}

// ============================================================================
// IndexedDB Local Persistence Engine
// ============================================================================
export class CoChemTelemetryDB {
  /**
   * IndexedDB wrapper for high-capacity telemetry archiving.
   */
  constructor(dbName = 'CoChemTelemetryDB', version = 1) {
    this.dbName = dbName;
    this.version = version;
    this.db = null;
    this.initPromise = this._initDB();
  }

  async _initDB() {
    if (typeof indexedDB === 'undefined') {
      return null;
    }
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains('telemetry_logs')) {
          const store = db.createObjectStore('telemetry_logs', { keyPath: 'id', autoIncrement: true });
          store.createIndex('job_id', 'job_id', { unique: false });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('type', 'type', { unique: false });
        }
        if (!db.objectStoreNames.contains('job_metadata')) {
          db.createObjectStore('job_metadata', { keyPath: 'job_id' });
        }
      };

      request.onsuccess = (event) => {
        this.db = event.target.result;
        resolve(this.db);
      };

      request.onerror = (event) => {
        console.error('CoChemTelemetryDB initialization error:', event.target.error);
        reject(event.target.error);
      };
    });
  }

  async appendLogs(logEntries) {
    if (!logEntries || logEntries.length === 0) return;
    const db = await this.initPromise;
    if (!db) return;

    return new Promise((resolve, reject) => {
      try {
        const tx = db.transaction(['telemetry_logs'], 'readwrite');
        const store = tx.objectStore('telemetry_logs');
        for (let i = 0; i < logEntries.length; i++) {
          store.add(logEntries[i]);
        }
        tx.oncomplete = () => resolve();
        tx.onerror = (e) => reject(e.target.error);
      } catch (err) {
        reject(err);
      }
    });
  }

  async getLogsForJob(jobId, limit = 5000) {
    const db = await this.initPromise;
    if (!db) return [];

    return new Promise((resolve, reject) => {
      try {
        const tx = db.transaction(['telemetry_logs'], 'readonly');
        const store = tx.objectStore('telemetry_logs');
        const index = store.index('job_id');
        const range = IDBKeyRange.only(jobId);
        const results = [];

        const cursorRequest = index.openCursor(range, 'prev');
        cursorRequest.onsuccess = (e) => {
          const cursor = e.target.result;
          if (cursor && results.length < limit) {
            results.push(cursor.value);
            cursor.continue();
          } else {
            resolve(results.reverse());
          }
        };
        cursorRequest.onerror = (e) => reject(e.target.error);
      } catch (err) {
        reject(err);
      }
    });
  }

  async clearJobLogs(jobId) {
    const db = await this.initPromise;
    if (!db) return;

    return new Promise((resolve, reject) => {
      try {
        const tx = db.transaction(['telemetry_logs'], 'readwrite');
        const store = tx.objectStore('telemetry_logs');
        const index = store.index('job_id');
        const range = IDBKeyRange.only(jobId);

        const req = index.openKeyCursor(range);
        req.onsuccess = (e) => {
          const cursor = e.target.result;
          if (cursor) {
            store.delete(cursor.primaryKey);
            cursor.continue();
          } else {
            resolve();
          }
        };
        req.onerror = (e) => reject(e.target.error);
      } catch (err) {
        reject(err);
      }
    });
  }
}

// ============================================================================
// Resilient WebSocket Hook
// ============================================================================
export function useResilientWebSocket(url, options = {}) {
  const {
    jobId = null,
    onMessage = null,
    autoConnect = true,
    reconnectInterval = DEFAULT_WS_RECONNECT_INTERVAL_MS,
    maxReconnectInterval = MAX_WS_RECONNECT_INTERVAL_MS,
    pingInterval = HEARTBEAT_PING_INTERVAL_MS,
  } = options;

  const [status, setStatus] = useState('DISCONNECTED'); // CONNECTING, CONNECTED, RECONNECTING, DISCONNECTED, ERROR
  const [reconnectCount, setReconnectCount] = useState(0);
  const [lastHeartbeat, setLastHeartbeat] = useState(null);

  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const currentIntervalRef = useRef(reconnectInterval);
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    let targetUrl = url;
    if (!targetUrl) {
      const loc = typeof window !== 'undefined' ? window.location : { hostname: '127.0.0.1', port: '8000', protocol: 'http:' };
      const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = loc.host || '127.0.0.1:8000';
      targetUrl = `${wsProto}//${wsHost}/ws/telemetry${jobId ? `/${jobId}` : ''}`;
    }

    setStatus('CONNECTING');

    try {
      const ws = new WebSocket(targetUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setStatus('CONNECTED');
        currentIntervalRef.current = reconnectInterval;
        setReconnectCount(0);
        setLastHeartbeat(Date.now());

        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, pingInterval);
      };

      ws.onmessage = (event) => {
        if (event.data === 'pong') {
          setLastHeartbeat(Date.now());
          return;
        }
        if (onMessageRef.current) {
          onMessageRef.current(event.data);
        }
      };

      ws.onerror = (err) => {
        console.warn('CoChem WebSocket Error:', err);
        setStatus('ERROR');
      };

      ws.onclose = (event) => {
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

        if (autoConnect) {
          setStatus('RECONNECTING');
          const nextInterval = Math.min(maxReconnectInterval, currentIntervalRef.current * 1.5);
          currentIntervalRef.current = nextInterval;
          setReconnectCount((prev) => prev + 1);

          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, currentIntervalRef.current + Math.random() * 500);
        } else {
          setStatus('DISCONNECTED');
        }
      };
    } catch (e) {
      console.error('Failed to instantiate WebSocket:', e);
      setStatus('ERROR');
    }
  }, [url, jobId, autoConnect, reconnectInterval, maxReconnectInterval, pingInterval]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setStatus('DISCONNECTED');
  }, []);

  const send = useCallback((data) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  const flush = useCallback(() => {
    return send('flush');
  }, [send]);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [connect, disconnect, autoConnect]);

  return {
    status,
    reconnectCount,
    lastHeartbeat,
    connect,
    disconnect,
    send,
    flush,
  };
}

// ============================================================================
// UI Component: Telemetry Metrics Panel
// ============================================================================
export function TelemetryMetricsPanel({ latestMetric, bufferStats, activeJobId }) {
  const energyHartree = latestMetric?.energy_hartree;
  const energyEv = energyHartree != null ? (energyHartree * HARTREE_TO_EV).toFixed(4) : null;
  const energyKcal = energyHartree != null ? (energyHartree * HARTREE_TO_KCAL_MOL).toFixed(2) : null;
  const deltaE = latestMetric?.delta_energy != null ? latestMetric.delta_energy.toExponential(4) : '--';
  const maxGrad = latestMetric?.max_gradient != null ? latestMetric.max_gradient.toExponential(4) : '--';
  const rmsGrad = latestMetric?.rms_gradient != null ? latestMetric.rms_gradient.toExponential(4) : '--';
  const step = latestMetric?.step ?? '--';
  const walltime = latestMetric?.walltime_seconds != null ? `${latestMetric.walltime_seconds.toFixed(2)}s` : '--';

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-zinc-100 font-sans shadow-md">
      <div className="flex flex-col bg-zinc-950/80 p-2.5 rounded border border-zinc-800/80">
        <span className="text-[11px] font-semibold uppercase text-zinc-400 tracking-wider">Step / Cycle</span>
        <span className="text-xl font-bold font-mono text-emerald-400 mt-0.5">{step}</span>
        <span className="text-[10px] text-zinc-500 truncate">{activeJobId || 'Global Stream'}</span>
      </div>

      <div className="flex flex-col bg-zinc-950/80 p-2.5 rounded border border-zinc-800/80">
        <span className="text-[11px] font-semibold uppercase text-zinc-400 tracking-wider">Energy (Hartree)</span>
        <span className="text-xl font-bold font-mono text-cyan-400 mt-0.5 truncate">
          {energyHartree != null ? energyHartree.toFixed(6) : '--'}
        </span>
        <span className="text-[10px] text-zinc-500 truncate">{energyEv ? `${energyEv} eV | ${energyKcal} kcal/mol` : 'Awaiting SCF'}</span>
      </div>

      <div className="flex flex-col bg-zinc-950/80 p-2.5 rounded border border-zinc-800/80">
        <span className="text-[11px] font-semibold uppercase text-zinc-400 tracking-wider">Δ Energy</span>
        <span className="text-xl font-bold font-mono text-amber-400 mt-0.5">{deltaE}</span>
        <span className="text-[10px] text-zinc-500">Eh convergence</span>
      </div>

      <div className="flex flex-col bg-zinc-950/80 p-2.5 rounded border border-zinc-800/80">
        <span className="text-[11px] font-semibold uppercase text-zinc-400 tracking-wider">Max Gradient</span>
        <span className="text-xl font-bold font-mono text-indigo-400 mt-0.5">{maxGrad}</span>
        <span className="text-[10px] text-zinc-500">Eh/Bohr (Tol: 1e-4)</span>
      </div>

      <div className="flex flex-col bg-zinc-950/80 p-2.5 rounded border border-zinc-800/80">
        <span className="text-[11px] font-semibold uppercase text-zinc-400 tracking-wider">RMS Gradient</span>
        <span className="text-xl font-bold font-mono text-violet-400 mt-0.5">{rmsGrad}</span>
        <span className="text-[10px] text-zinc-500">Eh/Bohr (Tol: 3e-5)</span>
      </div>

      <div className="flex flex-col bg-zinc-950/80 p-2.5 rounded border border-zinc-800/80">
        <span className="text-[11px] font-semibold uppercase text-zinc-400 tracking-wider">Walltime</span>
        <span className="text-xl font-bold font-mono text-rose-400 mt-0.5">{walltime}</span>
        <span className="text-[10px] text-zinc-500">Compute duration</span>
      </div>

      <div className="flex flex-col bg-zinc-950/80 p-2.5 rounded border border-zinc-800/80">
        <span className="text-[11px] font-semibold uppercase text-zinc-400 tracking-wider">Ring Buffer</span>
        <div className="flex items-baseline justify-between mt-0.5">
          <span className="text-lg font-bold font-mono text-teal-400">
            {bufferStats.size} / {bufferStats.capacity}
          </span>
          <span className="text-[10px] font-mono text-zinc-400">{bufferStats.usagePercent}%</span>
        </div>
        <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-1">
          <div
            className={`h-full transition-all duration-300 ${
              bufferStats.usagePercent > 90 ? 'bg-amber-500' : 'bg-teal-500'
            }`}
            style={{ width: `${bufferStats.usagePercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// UI Component: Log Stream Console Viewer
// ============================================================================
export function LogStreamViewer({
  logs,
  autoScroll,
  onToggleAutoScroll,
  onClear,
  onFlush,
  unreadCount,
  filterQuery,
  onFilterChange,
  logLevel,
  onLogLevelChange,
}) {
  const containerRef = useRef(null);
  const scrollAnchorRef = useRef(null);

  const filteredLogs = useMemo(() => {
    if (!filterQuery && logLevel === 'ALL') return logs;
    const query = filterQuery.toLowerCase();

    return logs.filter((entry) => {
      const text = entry.rawText || JSON.stringify(entry);
      const matchesText = !query || text.toLowerCase().includes(query);

      let matchesLevel = true;
      if (logLevel !== 'ALL') {
        const type = entry.type || 'stdout';
        if (logLevel === 'SCF') matchesLevel = type === 'scf_step';
        else if (logLevel === 'GRAD') matchesLevel = type === 'gradient' || text.includes('GRADIENT');
        else if (logLevel === 'WARN') matchesLevel = type === 'warning' || text.includes('WARN');
        else if (logLevel === 'ERROR') matchesLevel = type === 'error' || text.includes('ERROR') || text.includes('FATAL');
      }

      return matchesText && matchesLevel;
    });
  }, [logs, filterQuery, logLevel]);

  // Handle auto-scrolling
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [filteredLogs, autoScroll]);

  // Detect user scroll up vs bottom
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 30;
    if (autoScroll && !isAtBottom) {
      onToggleAutoScroll(false);
    } else if (!autoScroll && isAtBottom) {
      onToggleAutoScroll(true);
    }
  };

  const renderLogLine = (entry, index) => {
    const isJson = entry.isJson;
    const type = entry.type || 'stdout';
    const text = entry.rawText;
    const timestamp = entry.timestamp ? new Date(entry.timestamp * 1000).toLocaleTimeString() : '';

    let badgeColor = 'bg-zinc-800 text-zinc-400';
    if (type === 'scf_step') badgeColor = 'bg-emerald-950 text-emerald-300 border border-emerald-800/60';
    else if (type === 'lttb_batch') badgeColor = 'bg-cyan-950 text-cyan-300 border border-cyan-800/60';
    else if (type === 'error' || text?.includes('ERROR')) badgeColor = 'bg-rose-950 text-rose-300 border border-rose-800/60';
    else if (type === 'warning' || text?.includes('WARN')) badgeColor = 'bg-amber-950 text-amber-300 border border-amber-800/60';

    return (
      <div key={entry.id || index} className="flex items-start hover:bg-zinc-800/50 py-0.5 px-2 rounded font-mono text-[13px] leading-tight">
        <span className="select-none text-zinc-600 text-[11px] w-12 text-right mr-3 font-mono">
          {index + 1}
        </span>
        {timestamp && <span className="select-none text-zinc-500 text-[11px] mr-2">[{timestamp}]</span>}
        <span className={`select-none px-1.5 py-0.2 mr-2 text-[10px] uppercase font-bold rounded ${badgeColor}`}>
          {type}
        </span>
        <span className="flex-1 text-zinc-200 break-all whitespace-pre-wrap">
          {text}
        </span>
      </div>
    );
  };

  return (
    <div className="flex flex-col flex-1 bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden relative shadow-inner">
      {/* Console Toolbar */}
      <div className="flex flex-wrap items-center justify-between bg-zinc-900/90 border-b border-zinc-800 p-2 gap-2 text-xs">
        <div className="flex items-center gap-2">
          <input
            type="text"
            aria-label="Filter logs by regex or text"
            value={filterQuery}
            onChange={(e) => onFilterChange(e.target.value)}
            className="bg-zinc-950 border border-zinc-700 text-zinc-200 px-2.5 py-1 rounded text-xs focus:outline-none focus:border-cyan-500 w-48 sm:w-64"
          />
          <select
            value={logLevel}
            onChange={(e) => onLogLevelChange(e.target.value)}
            className="bg-zinc-950 border border-zinc-700 text-zinc-300 px-2 py-1 rounded text-xs focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Levels</option>
            <option value="SCF">SCF Cycles</option>
            <option value="GRAD">Gradients</option>
            <option value="WARN">Warnings</option>
            <option value="ERROR">Errors</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onFlush}
            title="Send flush frame to drain server buffer"
            className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded font-medium transition"
          >
            Flush Buffer
          </button>
          <button
            onClick={onClear}
            className="px-2.5 py-1 bg-zinc-800 hover:bg-rose-900/40 text-rose-300 rounded font-medium transition"
          >
            Clear Console
          </button>
          <button
            onClick={() => onToggleAutoScroll(!autoScroll)}
            className={`px-3 py-1 rounded font-medium transition ${
              autoScroll ? 'bg-cyan-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {autoScroll ? 'Auto-Scroll ON' : 'Auto-Scroll PAUSED'}
          </button>
        </div>
      </div>

      {/* Log lines container */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-2 bg-black/60 font-mono text-zinc-300 select-text"
        style={{ minHeight: '380px', maxHeight: '620px' }}
      >
        {filteredLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-600 text-sm italic py-24">
            No telemetry stream events captured. Listening on WebSocket...
          </div>
        ) : (
          filteredLogs.map(renderLogLine)
        )}
        <div ref={scrollAnchorRef} />
      </div>

      {/* Floating unread auto-scroll resume badge */}
      {!autoScroll && unreadCount > 0 && (
        <button
          onClick={() => onToggleAutoScroll(true)}
          className="absolute bottom-4 right-6 bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-1.5 rounded-full shadow-lg text-xs font-bold flex items-center gap-2 animate-bounce transition"
        >
          <span>↓ Resume Auto-Scroll ({unreadCount} new events)</span>
        </button>
      )}
    </div>
  );
}

// ============================================================================
// UI Component: Job Control & Dual-Mode Queue Panel
// ============================================================================
export function JobControlPanel({ apiBaseUrl = '', onJobSelect, activeJobId }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [engine, setEngine] = useState('ORCA');
  const [calcType, setCalcType] = useState('optimization');
  const [inputFile, setInputFile] = useState('molecule.xyz');
  const [functional, setFunctional] = useState('r2SCAN-3c');
  const [basis, setBasis] = useState('def2-TZVP');
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/v1/jobs?limit=25`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data.jobs || []);
      }
    } catch (err) {
      console.warn('Failed to fetch jobs list:', err);
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handleSubmitJob = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setStatusMessage(null);

    const payload = {
      engine,
      calculation_type: calcType,
      input_file: inputFile,
      parameters: {
        functional,
        basis,
        dispersion: 'D4',
      },
      priority: 5,
    };

    try {
      const res = await fetch(`${apiBaseUrl}/api/v1/jobs/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        setStatusMessage(`Job ${data.job_id} submitted successfully (${data.queue_mode})`);
        fetchJobs();
        if (onJobSelect) onJobSelect(data.job_id);
      } else {
        setStatusMessage(`Failed to submit job: HTTP ${res.status}`);
      }
    } catch (err) {
      setStatusMessage(`Submission error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelJob = async (jobId) => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/v1/jobs/cancel/${jobId}`, {
        method: 'POST',
      });
      if (res.ok) {
        fetchJobs();
      }
    } catch (err) {
      console.error('Failed to cancel job:', err);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 bg-zinc-900 border border-zinc-800 rounded-lg p-4 text-zinc-200">
      {/* Job Submission Form */}
      <form onSubmit={handleSubmitJob} className="flex flex-col gap-3 bg-zinc-950 p-3.5 rounded border border-zinc-800">
        <span className="text-xs font-bold uppercase text-zinc-400 tracking-wider">Submit Quantum Job</span>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[11px] text-zinc-400 block mb-1">Engine</label>
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded p-1.5 focus:outline-none focus:border-cyan-500"
            >
              <option value="ORCA">ORCA 6.1.1</option>
              <option value="CFOUR">CFOUR</option>
              <option value="xTB">g-xTB (GFN2)</option>
              <option value="AIMNet2">AIMNet2</option>
              <option value="MACE">MACE-MP(0)</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] text-zinc-400 block mb-1">Calculation Type</label>
            <select
              value={calcType}
              onChange={(e) => setCalcType(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded p-1.5 focus:outline-none focus:border-cyan-500"
            >
              <option value="optimization">Geometry Opt</option>
              <option value="sp">Single Point</option>
              <option value="frequency">NumFreq (Vibrational)</option>
              <option value="vpt2">VPT2 Anharmonic</option>
            </select>
          </div>
        </div>

        <div>
          <label className="text-[11px] text-zinc-400 block mb-1">Geometry Input File</label>
          <input
            type="text"
            aria-label="Geometry input file path"
            value={inputFile}
            onChange={(e) => setInputFile(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded p-1.5 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[11px] text-zinc-400 block mb-1">Functional / Method</label>
            <input
              type="text"
              value={functional}
              onChange={(e) => setFunctional(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded p-1.5 focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div>
            <label className="text-[11px] text-zinc-400 block mb-1">Basis Set</label>
            <input
              type="text"
              value={basis}
              onChange={(e) => setBasis(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs rounded p-1.5 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-1 w-full bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-800 text-white text-xs font-bold py-2 rounded transition"
        >
          {submitting ? 'Submitting...' : 'Dispatch to Queue'}
        </button>

        {statusMessage && <div className="text-[11px] text-cyan-400 font-mono mt-1">{statusMessage}</div>}
      </form>

      {/* Queue Job Table */}
      <div className="lg:col-span-2 flex flex-col bg-zinc-950 p-3.5 rounded border border-zinc-800 overflow-hidden">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold uppercase text-zinc-400 tracking-wider">
            Dual-Mode Job Execution Queue ({jobs.length})
          </span>
          <button onClick={fetchJobs} className="text-xs text-cyan-400 hover:underline">
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        <div className="overflow-x-auto flex-1 max-h-56">
          <table className="w-full text-left text-xs border-collapse font-sans">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400 text-[11px]">
                <th className="pb-1.5 font-medium">Job ID</th>
                <th className="pb-1.5 font-medium">Engine</th>
                <th className="pb-1.5 font-medium">Type</th>
                <th className="pb-1.5 font-medium">Status</th>
                <th className="pb-1.5 font-medium">Progress</th>
                <th className="pb-1.5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 font-mono text-[12px]">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-6 text-center text-zinc-600 italic">
                    No active or queued jobs found.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => {
                  const isSelected = job.job_id === activeJobId;
                  return (
                    <tr
                      key={job.job_id}
                      onClick={() => onJobSelect && onJobSelect(job.job_id)}
                      className={`cursor-pointer hover:bg-zinc-900 transition ${isSelected ? 'bg-zinc-800/80' : ''}`}
                    >
                      <td className="py-1.5 text-cyan-300 font-bold truncate max-w-[120px]">{job.job_id}</td>
                      <td className="py-1.5 text-zinc-300">{job.engine}</td>
                      <td className="py-1.5 text-zinc-400">{job.calculation_type}</td>
                      <td className="py-1.5">
                        <span
                          className={`px-1.5 py-0.5 text-[10px] rounded uppercase font-bold ${
                            job.status === 'completed'
                              ? 'bg-emerald-950 text-emerald-300'
                              : job.status === 'running'
                              ? 'bg-cyan-950 text-cyan-300 animate-pulse'
                              : job.status === 'cancelled'
                              ? 'bg-rose-950 text-rose-300'
                              : 'bg-zinc-800 text-zinc-400'
                          }`}
                        >
                          {job.status}
                        </span>
                      </td>
                      <td className="py-1.5 w-24">
                        <div className="w-full bg-zinc-800 h-1.5 rounded overflow-hidden">
                          <div
                            className="bg-cyan-500 h-full"
                            style={{ width: `${Math.round((job.progress || 0) * 100)}%` }}
                          />
                        </div>
                      </td>
                      <td className="py-1.5 text-right">
                        {job.status !== 'completed' && job.status !== 'cancelled' && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCancelJob(job.job_id);
                            }}
                            className="px-2 py-0.5 text-[10px] bg-rose-950/60 hover:bg-rose-900 text-rose-300 rounded border border-rose-800/60"
                          >
                            Cancel
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Application Component: CoChemDockTelemetryUI
// ============================================================================
export default function CoChemDockTelemetryUI({
  wsUrl = null,
  apiBaseUrl = '',
  maxBufferSize = DEFAULT_BUFFER_CAPACITY,
  enableIndexedDB = true,
}) {
  const [activeJobId, setActiveJobId] = useState(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filterQuery, setFilterQuery] = useState('');
  const [logLevel, setLogLevel] = useState('ALL');
  const [latestMetric, setLatestMetric] = useState(null);
  const [displayedLogs, setDisplayedLogs] = useState([]);
  const [bufferStats, setBufferStats] = useState({ size: 0, capacity: maxBufferSize, usagePercent: 0 });

  // References for memory protection & throttling
  const ringBufferRef = useRef(new RingBuffer(maxBufferSize));
  const indexedDbRef = useRef(enableIndexedDB ? new CoChemTelemetryDB() : null);
  const incomingQueueRef = useRef([]);
  const throttleRafRef = useRef(null);
  const unreadCountRef = useRef(0);
  const autoScrollRef = useRef(autoScroll);

  useEffect(() => {
    autoScrollRef.current = autoScroll;
    if (autoScroll) {
      unreadCountRef.current = 0;
      setUnreadCount(0);
    }
  }, [autoScroll]);

  // Flush incoming packet queue to RingBuffer and state using RequestAnimationFrame
  const processQueue = useCallback(() => {
    if (incomingQueueRef.current.length === 0) {
      throttleRafRef.current = null;
      return;
    }

    const batch = incomingQueueRef.current.splice(0, incomingQueueRef.current.length);
    ringBufferRef.current.pushBatch(batch);

    if (indexedDbRef.current) {
      indexedDbRef.current.appendLogs(batch).catch((err) => console.warn('IndexedDB write warning:', err));
    }

    setDisplayedLogs([...ringBufferRef.current.getItems()]);
    setBufferStats(ringBufferRef.current.stats);

    if (!autoScrollRef.current) {
      unreadCountRef.current += batch.length;
      setUnreadCount(unreadCountRef.current);
    }

    throttleRafRef.current = null;
  }, []);

  const scheduleFlush = useCallback(() => {
    if (!throttleRafRef.current) {
      throttleRafRef.current = requestAnimationFrame(processQueue);
    }
  }, [processQueue]);

  // Ingest incoming WebSocket message payload
  const handleIncomingMessage = useCallback(
    (rawMessage) => {
      const now = Date.now() / 1000;
      let entry = null;

      try {
        const parsed = JSON.parse(rawMessage);
        if (typeof parsed === 'object' && parsed !== null) {
          if (parsed.type === 'lttb_batch' && Array.isArray(parsed.data)) {
            // LTTB batched stream
            parsed.data.forEach((sub) => handleIncomingMessage(sub));
            return;
          }

          entry = {
            id: `${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
            isJson: true,
            type: parsed.type || 'telemetry',
            timestamp: parsed.timestamp || now,
            job_id: parsed.job_id || activeJobId,
            rawText: JSON.stringify(parsed),
            payload: parsed,
          };

          if (parsed.type === 'scf_step' || parsed.energy_hartree != null) {
            setLatestMetric(parsed);
          }
        }
      } catch (err) {
        // Raw stdout line
        entry = {
          id: `${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
          isJson: false,
          type: 'stdout',
          timestamp: now,
          job_id: activeJobId,
          rawText: rawMessage,
          payload: null,
        };
      }

      if (entry) {
        incomingQueueRef.current.push(entry);
        scheduleFlush();
      }
    },
    [activeJobId, scheduleFlush]
  );

  const { status: wsStatus, reconnectCount, flush: triggerWsFlush, connect: wsConnect, disconnect: wsDisconnect } =
    useResilientWebSocket(wsUrl, {
      jobId: activeJobId,
      onMessage: handleIncomingMessage,
      autoConnect: true,
    });

  const handleClear = () => {
    ringBufferRef.current.clear();
    setDisplayedLogs([]);
    setBufferStats(ringBufferRef.current.stats);
    unreadCountRef.current = 0;
    setUnreadCount(0);
  };

  const handleExportLogs = () => {
    const lines = displayedLogs.map((l) => l.rawText).join('\n');
    const blob = new Blob([lines], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cochem_telemetry_${activeJobId || 'session'}_${Date.now()}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-screen w-full bg-zinc-950 text-zinc-100 font-sans p-4 gap-4 overflow-hidden">
      {/* Top Header Navigation Bar */}
      <header className="flex flex-wrap items-center justify-between bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2.5 shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse shadow-cyan-500/50" />
          <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
            <span>CoChem-DOCK</span>
            <span className="text-xs px-2 py-0.5 bg-zinc-800 text-cyan-300 rounded font-mono font-normal">
              Crash-Proof Telemetry Console
            </span>
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-mono">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                wsStatus === 'CONNECTED'
                  ? 'bg-emerald-500 shadow-emerald-500/50'
                  : wsStatus === 'CONNECTING' || wsStatus === 'RECONNECTING'
                  ? 'bg-amber-500 animate-ping'
                  : 'bg-rose-500'
              }`}
            />
            <span className="text-zinc-300">{wsStatus}</span>
            {reconnectCount > 0 && <span className="text-zinc-500">(Retries: {reconnectCount})</span>}
          </div>

          <button
            onClick={wsStatus === 'CONNECTED' ? wsDisconnect : wsConnect}
            className="px-2.5 py-1 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded font-medium transition"
          >
            {wsStatus === 'CONNECTED' ? 'Disconnect' : 'Connect'}
          </button>

          <button
            onClick={handleExportLogs}
            className="px-2.5 py-1 text-xs bg-cyan-900/60 hover:bg-cyan-800 text-cyan-200 rounded font-medium border border-cyan-700/60 transition"
          >
            Export Log (.log)
          </button>
        </div>
      </header>

      {/* Real-Time Telemetry Metric Badges */}
      <TelemetryMetricsPanel latestMetric={latestMetric} bufferStats={bufferStats} activeJobId={activeJobId} />

      {/* Main Console Viewport */}
      <LogStreamViewer
        logs={displayedLogs}
        autoScroll={autoScroll}
        onToggleAutoScroll={setAutoScroll}
        onClear={handleClear}
        onFlush={triggerWsFlush}
        unreadCount={unreadCount}
        filterQuery={filterQuery}
        onFilterChange={setFilterQuery}
        logLevel={logLevel}
        onLogLevelChange={setLogLevel}
      />

      {/* Job Management & Queue Panel */}
      <JobControlPanel apiBaseUrl={apiBaseUrl} onJobSelect={setActiveJobId} activeJobId={activeJobId} />
    </div>
  );
}

// ============================================================================
// Standalone Mounting Bridge for Zero-Build Environments
// ============================================================================
export function mountCoChemTelemetryUI(containerElement, options = {}) {
  if (typeof window === 'undefined' || !containerElement) return;
  if (window.ReactDOM && window.ReactDOM.createRoot) {
    const root = window.ReactDOM.createRoot(containerElement);
    root.render(React.createElement(CoChemDockTelemetryUI, options));
    return root;
  } else if (window.ReactDOM && window.ReactDOM.render) {
    window.ReactDOM.render(React.createElement(CoChemDockTelemetryUI, options), containerElement);
  }
}

if (typeof window !== 'undefined') {
  window.CoChemDockTelemetryUI = CoChemDockTelemetryUI;
  window.mountCoChemTelemetryUI = mountCoChemTelemetryUI;
}
