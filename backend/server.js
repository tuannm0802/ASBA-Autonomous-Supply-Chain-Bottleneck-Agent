/**
 * ASBA Express API Server
 * ━━━━━━━━━━━━━━━━━━━━━━━
 * Serves routes for historical assessment runs and triggering new predictions.
 */

const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;

// Resolve python executable from virtual environment if present
const getPythonExecutable = () => {
  const winVenvPython = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
  const nixVenvPython = path.join(__dirname, '..', '.venv', 'bin', 'python');
  
  if (fs.existsSync(winVenvPython)) {
    console.log(`[PYTHON] Found Windows virtual environment python: ${winVenvPython}`);
    return winVenvPython;
  } else if (fs.existsSync(nixVenvPython)) {
    console.log(`[PYTHON] Found Unix virtual environment python: ${nixVenvPython}`);
    return nixVenvPython;
  }
  
  console.log('[PYTHON] Virtual environment python not found. Defaulting to system "python"');
  return 'python';
};

const pythonCmd = getPythonExecutable();

// Robust extraction of JSON from child process stdout
const extractJson = (stdout) => {
  const match = stdout.match(/===REPORT_START===([\s\S]*?)===REPORT_END===/);
  if (match) {
    return match[1].trim();
  }
  const startIdx = stdout.indexOf('{');
  const endIdx = stdout.lastIndexOf('}');
  if (startIdx !== -1 && endIdx !== -1 && endIdx >= startIdx) {
    return stdout.slice(startIdx, endIdx + 1);
  }
  throw new Error('No JSON object found in output');
};

// Enable CORS for all routes (so React app at localhost:5173 can query)
app.use(cors());
app.use(express.json());

const reportsDir = path.join(__dirname, '..', 'daily_reports');
if (!fs.existsSync(reportsDir)) {
  fs.mkdirSync(reportsDir, { recursive: true });
}

// ── GET /api/history ──────────────────────────────────────────
// Scans the daily_reports/ folder and returns details of all past runs.
app.get('/api/history', (req, res) => {
  try {
    if (!fs.existsSync(reportsDir)) {
      return res.json([]);
    }

    const files = fs.readdirSync(reportsDir).filter(f => f.endsWith('.json'));
    
    const history = files.map(file => {
      const filePath = path.join(reportsDir, file);
      try {
        const content = fs.readFileSync(filePath, 'utf8');
        const data = JSON.parse(content);
        
        // Extract summary metadata for listing
        return {
          filename: file,
          date: data.date || file.replace('report_', '').replace('.json', ''),
          accuracy: data.metrics?.accuracy || 0,
          f1_score: data.metrics?.f1_score || 0,
          auc_roc: data.metrics?.auc_roc || 0,
          balancing_method: data.metrics?.balancing_method || 'Unknown',
          high_risk_count: data.high_risk_orders ? data.high_risk_orders.length : 0,
          total_orders: data.predictions_summary?.total_current_orders || 0,
          data: data // Send full payload
        };
      } catch (err) {
        console.error(`Error reading/parsing report file ${file}:`, err);
        return null;
      }
    }).filter(Boolean);

    // Sort by date descending
    history.sort((a, b) => b.date.localeCompare(a.date));
    res.json(history);
  } catch (error) {
    console.error('Failed to retrieve history:', error);
    res.status(500).json({ error: 'Failed to retrieve historical reports' });
  }
});

// ── POST /api/generate-prediction ─────────────────────────────
// Spawns the Python child process to execute the ML pipeline & Gemini Agent.
app.post('/api/generate-prediction', (req, res) => {
  console.log('Triggering daily Supply Chain Risk assessment...');

  // Spawn run_pipeline.py
  const pythonProcess = spawn(pythonCmd, ['run_pipeline.py'], {
    cwd: __dirname,
    env: { ...process.env } // Pass GOOGLE_API_KEY and other env vars
  });

  let stdoutData = '';
  let stderrData = '';

  pythonProcess.stdout.on('data', (data) => {
    stdoutData += data.toString();
  });

  pythonProcess.stderr.on('data', (data) => {
    stderrData += data.toString();
    console.error(`[Python stderr] ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python script exited with code ${code}`);
    
    if (code !== 0) {
      console.error('Python execution failed. Stderr output:', stderrData);
      return res.status(500).json({
        error: `Python pipeline script failed with exit code ${code}`,
        stderr: stderrData,
        stdout: stdoutData
      });
    }

    try {
      const jsonString = extractJson(stdoutData);
      const result = JSON.parse(jsonString);
      
      // Extract date to save the report locally
      const todayDateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      const reportFilename = `report_${todayDateStr}.json`;
      const reportPath = path.join(reportsDir, reportFilename);
      
      fs.writeFileSync(reportPath, JSON.stringify(result, null, 2), 'utf8');
      console.log(`Saved daily report: ${reportFilename}`);

      res.json(result);
    } catch (parseError) {
      console.error('Failed to parse Python JSON output:', parseError);
      console.error('Raw stdout:', stdoutData);
      res.status(500).json({
        error: 'Failed to parse structured JSON from Python pipeline: ' + parseError.message,
        rawOutput: stdoutData,
        stderr: stderrData
      });
    }
  });
});

// ── POST /api/mitigate-order ──────────────────────────────────
// Mitigates an order (upgrades shipping, switches mills, or swaps B2B supplier)
// and re-runs model inference to calculate the updated risk probability.
app.post('/api/mitigate-order', (req, res) => {
  const { orderId, mitigationType, value } = req.body;
  
  // ── Input Validation / Sanitization (Security Safeguard) ──
  const orderIdRegex = /^ORD-\d{8}-[CH]\d{4}$/;
  const supplierIdRegex = /^SUP-\d{3}$/;
  const validMitigations = ['logistics', 'mill', 'supplier'];

  if (!orderId || !orderIdRegex.test(orderId)) {
    console.warn(`[SECURITY] Blocked invalid Order ID parameter: ${orderId}`);
    return res.status(400).json({ error: 'Invalid Order ID format. Expected ORD-YYYYMMDD-CXXXX or ORD-YYYYMMDD-HXXXX' });
  }

  const cleanMitigation = mitigationType ? mitigationType.trim().toLowerCase() : '';
  if (!cleanMitigation || !validMitigations.includes(cleanMitigation)) {
    console.warn(`[SECURITY] Blocked invalid Mitigation Type parameter: ${mitigationType}`);
    return res.status(400).json({ error: 'Invalid mitigation type. Expected logistics, mill, or supplier' });
  }

  if (cleanMitigation === 'supplier') {
    if (!value || !supplierIdRegex.test(value)) {
      console.warn(`[SECURITY] Blocked invalid Supplier ID value: ${value}`);
      return res.status(400).json({ error: 'Alternative supplier mitigation requires a valid Supplier ID (e.g., SUP-001)' });
    }
  }

  console.log(`[MITIGATION] Applying '${cleanMitigation}' to order '${orderId}'${value ? ` with value '${value}'` : ''}...`);
  
  const args = ['mitigate_order.py', orderId, cleanMitigation];
  if (value) {
    args.push(value);
  }
  
  const pythonProcess = spawn(pythonCmd, args, {
    cwd: __dirname,
    env: { ...process.env }
  });
  
  let stdoutData = '';
  let stderrData = '';
  
  pythonProcess.stdout.on('data', (data) => {
    stdoutData += data.toString();
  });
  
  pythonProcess.stderr.on('data', (data) => {
    stderrData += data.toString();
  });
  
  pythonProcess.on('close', (code) => {
    console.log(`Mitigation script exited with code ${code}`);
    if (code !== 0) {
      console.error(`Mitigation failed: ${stderrData}`);
      return res.status(500).json({ error: 'Mitigation failed: ' + stderrData });
    }
    
    try {
      const jsonString = extractJson(stdoutData);
      const result = JSON.parse(jsonString);
      res.json(result);
    } catch (err) {
      console.error('Failed to parse mitigation output:', err);
      console.error('Raw stdout:', stdoutData);
      res.status(500).json({ error: 'Failed to parse mitigation response' });
    }
  });
});

// ── POST /api/chat ────────────────────────────────────────────
// Conversational chat turn with the Sourcing Specialist Agent.
app.post('/api/chat', (req, res) => {
  const { message, history } = req.body;
  
  if (!message || typeof message !== 'string') {
    return res.status(400).json({ error: 'Message is required and must be a string.' });
  }
  
  const pythonProcess = spawn(pythonCmd, ['chat_agent.py'], {
    cwd: __dirname,
    env: { ...process.env }
  });
  
  let stdoutData = '';
  let stderrData = '';
  
  pythonProcess.stdout.on('data', (data) => {
    stdoutData += data.toString();
  });
  
  pythonProcess.stderr.on('data', (data) => {
    stderrData += data.toString();
  });
  
  // Write payload to stdin and close it
  const payload = JSON.stringify({ message, history: history || [] });
  pythonProcess.stdin.write(payload);
  pythonProcess.stdin.end();
  
  pythonProcess.on('close', (code) => {
    if (code !== 0) {
      console.error(`Chat agent process failed with code ${code}. Stderr: ${stderrData}`);
      return res.status(500).json({ error: 'Chat turn failed: ' + stderrData });
    }
    
    try {
      const match = stdoutData.match(/===CHAT_START===([\s\S]*?)===CHAT_END===/);
      if (match) {
        const result = JSON.parse(match[1].trim());
        return res.json(result);
      }
      
      const parsed = JSON.parse(stdoutData.trim());
      res.json(parsed);
    } catch (err) {
      console.error('Failed to parse chat output:', err);
      console.error('Raw stdout:', stdoutData);
      res.status(500).json({ error: 'Failed to parse chat response' });
    }
  });
});

// ── Serve static frontend assets in production ────────────────
const distPath = path.join(__dirname, '..', 'frontend', 'dist');
if (fs.existsSync(distPath)) {
  console.log(`[STATIC] Serving frontend static assets from ${distPath}`);
  app.use(express.static(distPath));
  // Catch-all route to serve index.html for client-side routing
  app.get('*', (req, res) => {
    res.sendFile(path.join(distPath, 'index.html'));
  });
} else {
  console.log(`[STATIC] Frontend build directory not found at ${distPath}. Running in API-only mode.`);
}

app.listen(PORT, () => {
  console.log(`ASBA Backend listening on port ${PORT}...`);
  console.log(`Environment GOOGLE_API_KEY is ${process.env.GOOGLE_API_KEY ? 'Present' : 'Missing'}`);
  
  // Trigger background assessment run on startup
  triggerBackgroundPrediction();
});

function triggerBackgroundPrediction() {
  console.log('[AUTO-TRIGGER] Launching daily assessment pipeline in the background on startup...');
  const pythonProcess = spawn(pythonCmd, ['run_pipeline.py'], {
    cwd: __dirname,
    env: { ...process.env }
  });
  
  let stdoutData = '';
  pythonProcess.stdout.on('data', (data) => { stdoutData += data.toString(); });
  pythonProcess.on('close', (code) => {
    console.log(`[AUTO-TRIGGER] Startup pipeline completed with exit code ${code}`);
    if (code === 0) {
      try {
        const jsonString = extractJson(stdoutData);
        const result = JSON.parse(jsonString);
        const todayDateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const reportFilename = `report_${todayDateStr}.json`;
        const reportPath = path.join(reportsDir, reportFilename);
        fs.writeFileSync(reportPath, JSON.stringify(result, null, 2), 'utf8');
        console.log(`[AUTO-TRIGGER] Saved startup report: ${reportFilename}`);
      } catch (err) {
        console.error('[AUTO-TRIGGER] Failed to parse/save startup report:', err);
      }
    }
  });
}
