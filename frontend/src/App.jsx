import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  AlertTriangle, 
  Award, 
  Calendar, 
  CheckCircle2, 
  ChevronDown, 
  ChevronUp, 
  Database, 
  FileText, 
  History, 
  Layers, 
  Play, 
  RefreshCw, 
  Scissors, 
  ShieldAlert, 
  Sparkles, 
  TrendingUp, 
  Truck,
  MessageSquare
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell, 
  BarChart, 
  Bar, 
  LineChart,
  Line,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend 
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://localhost:5000' : window.location.origin);

const b2bAlternatives = [
  { id: 'ALT-SUP-101', name: 'Apex Fabrics Ltd (Fabric_Body, Lead: 8d, Delay: 1.2%)', specialty: 'Fabric_Body' },
  { id: 'ALT-SUP-110', name: 'Summit Sourcing (Fabric_Body, Lead: 12d, Delay: 1.8%)', specialty: 'Fabric_Body' },
  { id: 'ALT-SUP-108', name: 'CoreThreads Textiles (Threads, Lead: 5d, Delay: 0.6%)', specialty: 'Threads' },
  { id: 'ALT-SUP-106', name: 'Prestige Trims (Sewing_Trims, Lead: 4d, Delay: 0.3%)', specialty: 'Sewing_Trims' },
  { id: 'ALT-SUP-107', name: 'SafePack Box & Tag (Packing_Trims, Lead: 4d, Delay: 0.2%)', specialty: 'Packing_Trims' },
  { id: 'ALT-SUP-103', name: 'Vibrant Ribbing (Fabric_Rib, Lead: 5d, Delay: 0.5%)', specialty: 'Fabric_Rib' },
  { id: 'ALT-SUP-104', name: 'Elite Trim Suppliers (Fabric_Trim, Lead: 6d, Delay: 0.8%)', specialty: 'Fabric_Trim' },
  { id: 'ALT-SUP-105', name: 'Apex Collar & Cuff (Fabric_CollarCuff, Lead: 7d, Delay: 1.1%)', specialty: 'Fabric_CollarCuff' },
  { id: 'ALT-SUP-109', name: 'Interlining Experts (Interlining, Lead: 6d, Delay: 0.9%)', specialty: 'Interlining' }
];

const getAltsForOrder = (order) => {
  let matched = [];
  if (order.Fabric_Body > 1500) matched = b2bAlternatives.filter(a => a.specialty === 'Fabric_Body');
  else if (order.Threads > 3000) matched = b2bAlternatives.filter(a => a.specialty === 'Threads');
  else if (order.Sewing_Trims > 1500) matched = b2bAlternatives.filter(a => a.specialty === 'Sewing_Trims');
  
  if (matched.length === 0) {
    matched = b2bAlternatives;
  }
  return matched;
};

export default function App() {
  const [activeTab, setActiveTab] = useState('today');
  const [history, setHistory] = useState([]);
  const [selectedHistIndex, setSelectedHistIndex] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [predictionData, setPredictionData] = useState(null);
  const [expandedOrder, setExpandedOrder] = useState(null);
  const [error, setError] = useState(null);

  // Chat States
  const [chatMessages, setChatMessages] = useState([
    {
      role: 'assistant',
      text: "Hello! I am your AI Sourcing Mitigation Specialist. I have access to our B2B Supplier Directory and historical risk models. How can I help you resolve today's garment supply chain bottlenecks?"
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatReasoning, setChatReasoning] = useState([]);

  // Auto-scroll chat console
  const chatEndRef = useRef(null);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, chatLoading]);

  // Mitigation States
  const [mitigationLoading, setMitigationLoading] = useState({});
  const [mitigationChoices, setMitigationChoices] = useState({});
  const [selectedSuppliers, setSelectedSuppliers] = useState({});

  const loadingSteps = [
    "Initializing Node.js Express & Python processes...",
    "Analyzing dataset class distribution (expecting ~7.5% imbalance)...",
    "Running SMOTE / CTGAN synthetic oversampling pipeline...",
    "Training XGBoost classifier & performing stratified evaluation...",
    "Predicting risk probabilities on today's active orders...",
    "Querying Google Gemini AI for supply chain bottlenecks & remediation advice..."
  ];

  useEffect(() => {
    fetchHistory();
  }, []);

  // Cycle through loading steps to show active agent thoughts
  useEffect(() => {
    let interval;
    if (loading) {
      setLoadingStep(0);
      interval = setInterval(() => {
        setLoadingStep(prev => (prev < loadingSteps.length - 1 ? prev + 1 : prev));
      }, 3500);
    }
    return () => clearInterval(interval);
  }, [loading]);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/history`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
        if (data.length > 0) {
          if (selectedHistIndex === -1) {
            setSelectedHistIndex(0);
          }
          // Set yesterday's dashboard by default on start
          if (!predictionData) {
            setPredictionData(data[0].data);
          }
        }
      }
    } catch (err) {
      console.error("Error fetching history:", err);
    }
  };

  const handleMitigate = async (orderId) => {
    const type = mitigationChoices[orderId] || 'logistics';
    const val = selectedSuppliers[orderId] || 'ALT-SUP-101';
    
    setMitigationLoading(prev => ({ ...prev, [orderId]: true }));
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/mitigate-order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orderId, mitigationType: type, value: type === 'supplier' ? val : undefined })
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Mitigation failed");
      }
      
      const result = await res.json();
      
      // Update local state predictionData
      if (predictionData) {
        const updatedOrders = predictionData.high_risk_orders.map(o => {
          if (o.Order_ID === orderId) {
            return {
              ...o,
              Supplier_ID: result.updated_features.Supplier_ID,
              Forwarder: result.updated_features.Forwarder,
              Mill_Source: result.updated_features.Mill_Source,
              Risk_Probability: result.new_probability,
              Risk_Level: result.new_risk_level,
              mitigated: true,
              mitigation_action: result.mitigation_applied,
              remediation_advice: `✔️ RISK MITIGATED: ${result.mitigation_applied}. Delivery risk successfully lowered to ${(result.new_probability * 100).toFixed(1)}% (${result.new_risk_level}).`
            };
          }
          return o;
        });
        
        // Recount active high-risk orders
        const activeCount = updatedOrders.filter(o => ['HIGH', 'CRITICAL'].includes(o.Risk_Level) && !o.mitigated).length;
        
        setPredictionData({
          ...predictionData,
          high_risk_orders: updatedOrders,
          predictions_summary: {
            ...predictionData.predictions_summary,
            high_risk_count: activeCount
          }
        });
      }
      
      // Refresh history dropdown
      fetchHistory();
      
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to apply mitigation.");
    } finally {
      setMitigationLoading(prev => ({ ...prev, [orderId]: false }));
    }
  };

  const runPrediction = async () => {
    setLoading(true);
    setError(null);
    setPredictionData(null);
    setExpandedOrder(null);
    try {
      const res = await fetch(`${API_BASE}/api/generate-prediction`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errObj = await res.json();
        throw new Error(errObj.error || "Execution failed");
      }
      const data = await res.json();
      setPredictionData(data);
      fetchHistory(); // Refresh historical logs dropdown
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to communicate with Express/Python backend.");
    } finally {
      setLoading(false);
    }
  };

  const handleSendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput.trim();
    setChatInput('');
    setChatLoading(true);

    // Update UI with user message
    const updatedMessages = [...chatMessages, { role: 'user', text: userMessage }];
    setChatMessages(updatedMessages);

    try {
      // Map message history to schema expected by backend
      const formattedHistory = chatMessages.map(m => ({
        role: m.role === 'assistant' ? 'model' : 'user',
        text: m.text
      }));

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          history: formattedHistory
        })
      });

      if (!res.ok) {
        throw new Error("Chat engine failed to respond.");
      }

      const result = await res.json();
      if (result.status === 'success' || result.status === 'partial_success') {
        setChatMessages(prev => [...prev, { role: 'assistant', text: result.response }]);
        if (result.reasoning_steps && result.reasoning_steps.length > 0) {
          setChatReasoning(result.reasoning_steps);
        }
      } else {
        throw new Error(result.message || "Failed to retrieve agent answer.");
      }

    } catch (err) {
      console.error(err);
      setChatMessages(prev => [...prev, { 
        role: 'assistant', 
        text: `⚠️ Error: ${err.message || "I had trouble contacting the backend agent. Please check if the server is running."}` 
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const getActiveData = () => {
    if (activeTab === 'today') {
      return predictionData;
    }
    if (activeTab === 'history' && history.length > 0 && selectedHistIndex !== -1) {
      return history[selectedHistIndex]?.data;
    }
    if (activeTab === 'analytics') {
      return predictionData || (selectedHistIndex !== -1 && history[selectedHistIndex]?.data) || null;
    }
    return null;
  };

  const data = getActiveData();

  // Curated color scheme variables
  const PIE_COLORS = ['#10b981', '#f59e0b', '#ef4444']; // Safe, Medium, High

  // Prepare Pie Chart data from active report
  const getPieData = () => {
    if (!data) return [];
    
    // Fallback if data structure is slightly different
    if (data.charts?.risk_distribution) {
      return data.charts.risk_distribution;
    }

    const breakdown = data.predictions_summary?.risk_level_breakdown || {};
    const low = breakdown.LOW || 0;
    const med = breakdown.MEDIUM || 0;
    const high = (breakdown.HIGH || 0) + (breakdown.CRITICAL || 0);
    
    return [
      { name: 'Low Risk', value: low },
      { name: 'Medium Risk', value: med },
      { name: 'High Risk', value: high },
    ];
  };

  const pieData = getPieData();

  // Prepare Forwarder Bottleneck data
  const getForwarderData = () => {
    if (!data) return [];
    if (data.charts?.bottleneck_by_forwarder) {
      return data.charts.bottleneck_by_forwarder;
    }
    // Aggregate manually from high-risk orders if charts data is absent
    const orders = data.high_risk_orders || [];
    const counts = { DHL: 0, ONE: 0, Wanhai: 0, Gemadept: 0 };
    orders.forEach(o => {
      if (counts[o.Forwarder] !== undefined) {
        counts[o.Forwarder]++;
      }
    });
    return Object.keys(counts).map(key => ({
      forwarder: key,
      high_risk_count: counts[key],
    }));
  };

  const forwarderData = getForwarderData();

  // Prepare Material Bottleneck data
  const getMaterialData = () => {
    if (!data) return [];
    if (data.charts?.bottleneck_by_material) {
      return data.charts.bottleneck_by_material;
    }
    // Fallback static-looking feature importances
    const features = data.top_risk_features || {};
    return Object.keys(features).map(key => ({
      material: key.replace('Fabric_', 'Fabric '),
      correlation: features[key],
    }));
  };

  const materialData = getMaterialData();

  const calculateLocalCosts = (order) => {
    const unitCount = order.Unit_Count || 5000;
    const orderVal = order.Order_Value_USD || 50000;
    const penaltyPerDay = order.Delay_Penalty_USD_Per_Day || 500;
    const origShipping = order.Shipping_Cost_USD || 3000;
    const origProb = order.Risk_Probability || 0.85;

    const calcExposure = (prob) => prob * (penaltyPerDay * 5.0 + orderVal * 0.15);

    return [
      {
        name: 'Original Sourcing',
        shipping: origShipping,
        premium: 0,
        exposure: Math.round(calcExposure(origProb)),
        total: Math.round(origShipping + calcExposure(origProb))
      },
      {
        name: 'DHL Upgrade',
        shipping: 10000,
        premium: 0,
        exposure: Math.round(calcExposure(0.02)),
        total: Math.round(10000 + calcExposure(0.02))
      },
      {
        name: 'Internal Sourcing',
        shipping: origShipping,
        premium: Math.round(unitCount * 0.50),
        exposure: Math.round(calcExposure(0.10)),
        total: Math.round(origShipping + unitCount * 0.50 + calcExposure(0.10))
      },
      {
        name: 'B2B Alternative',
        shipping: 3500,
        premium: Math.round(unitCount * 0.80),
        exposure: Math.round(calcExposure(0.04)),
        total: Math.round(3500 + unitCount * 0.80 + calcExposure(0.04))
      }
    ];
  };

  const getAnalyticsData = () => {
    if (!data) return null;
    const orders = data.high_risk_orders || [];
    
    // 1. Risk breakdown
    const breakdown = data.predictions_summary?.risk_level_breakdown || {};
    const riskBreakdown = [
      { name: 'Low', value: breakdown.LOW || 0 },
      { name: 'Medium', value: breakdown.MEDIUM || 0 },
      { name: 'High', value: breakdown.HIGH || 0 },
      { name: 'Critical', value: breakdown.CRITICAL || 0 }
    ];

    // 2. Feature importances
    let featureImportance = [];
    if (data.charts?.bottleneck_by_material) {
      featureImportance = data.charts.bottleneck_by_material.map(m => ({
        name: m.material.replace('Fabric_', '').replace('_Count', '').replace('Fwd_', '').replace('_USD', '').replace('Outsource_', 'Outsourced ').replace('Internal_', 'Internal '),
        value: m.correlation
      }));
    } else {
      const features = data.top_risk_features || {};
      featureImportance = Object.keys(features).map(k => ({
        name: k.replace('Fabric_', '').replace('_Count', '').replace('Fwd_', ''),
        value: features[k]
      }));
    }

    // 3. Train vs Test Samples
    const modelPerf = data.metrics || {};
    const samplesSplit = [
      { name: 'Training Set', count: modelPerf.training_samples || 0 },
      { name: 'Test Set', count: modelPerf.test_samples || 0 }
    ];

    // 4. Forwarder High Risk Counts
    const fwdCounts = { DHL: 0, ONE: 0, Wanhai: 0, Gemadept: 0 };
    orders.forEach(o => { if (fwdCounts[o.Forwarder] !== undefined) fwdCounts[o.Forwarder]++; });
    const fwdHighRisk = Object.keys(fwdCounts).map(k => ({ name: k, count: fwdCounts[k] }));

    // 5. Average Risk by Forwarder
    const fwdSums = { DHL: { sum: 0, count: 0 }, ONE: { sum: 0, count: 0 }, Wanhai: { sum: 0, count: 0 }, Gemadept: { sum: 0, count: 0 } };
    orders.forEach(o => {
      if (fwdSums[o.Forwarder]) {
        fwdSums[o.Forwarder].sum += o.Risk_Probability;
        fwdSums[o.Forwarder].count++;
      }
    });
    const fwdAvgRisk = Object.keys(fwdSums).map(k => ({
      name: k,
      risk: fwdSums[k].count > 0 ? parseFloat((fwdSums[k].sum / fwdSums[k].count).toFixed(2)) : 0
    }));

    // 6. Shipping Volume by Forwarder
    const fwdVols = { DHL: 0, ONE: 0, Wanhai: 0, Gemadept: 0 };
    orders.forEach(o => { if (fwdVols[o.Forwarder] !== undefined) fwdVols[o.Forwarder] += o.Unit_Count; });
    const fwdVolume = Object.keys(fwdVols).map(k => ({ name: k, value: fwdVols[k] }));

    // 7. Material Stock averages (Safe vs High Risk)
    let avgFabricHigh = 0, avgThreadsHigh = 0;
    if (orders.length > 0) {
      avgFabricHigh = Math.round(orders.reduce((sum, o) => sum + o.Fabric_Body, 0) / orders.length);
      avgThreadsHigh = Math.round(orders.reduce((sum, o) => sum + o.Threads, 0) / orders.length);
    }
    const materialStock = [
      { name: 'Fabric Body', Safe: 3800, HighRisk: avgFabricHigh || 1800 },
      { name: 'Threads', Safe: 4500, HighRisk: avgThreadsHigh || 2200 }
    ];

    // 8. Color Complexity vs Risk
    const complexityCounts = {};
    orders.forEach(o => {
      const sets = o.Color_Sets_Count;
      if (!complexityCounts[sets]) complexityCounts[sets] = { sum: 0, count: 0 };
      complexityCounts[sets].sum += o.Risk_Probability;
      complexityCounts[sets].count++;
    });
    const complexityRisk = Object.keys(complexityCounts).map(k => ({
      name: `${k} Colors`,
      risk: parseFloat((complexityCounts[k].sum / complexityCounts[k].count).toFixed(2))
    })).sort((a,b) => a.name.localeCompare(b.name));

    // 9. Mill Sourcing Mix
    const millCounts = { Internal: 0, Outsource: 0, Both: 0 };
    orders.forEach(o => { if (millCounts[o.Mill_Source] !== undefined) millCounts[o.Mill_Source]++; });
    const millMix = Object.keys(millCounts).map(k => ({ name: k, value: millCounts[k] }));

    // 10. Value at Risk by Supplier
    const supRiskValues = {};
    orders.forEach(o => {
      const sup = o.Supplier_ID;
      const exposure = o.Order_Value_USD * o.Risk_Probability;
      supRiskValues[sup] = (supRiskValues[sup] || 0) + exposure;
    });
    const supplierExposure = Object.keys(supRiskValues).map(k => ({
      name: k,
      value: Math.round(supRiskValues[k])
    })).sort((a,b) => b.value - a.value).slice(0, 5);

    // 11. Stacked Sourcing Cost for Top 5 orders
    const topOrdersCost = orders.slice(0, 5).map(o => {
      const riskExposure = Math.round(o.Risk_Probability * (o.Delay_Penalty_USD_Per_Day * 5 + o.Order_Value_USD * 0.15));
      return {
        name: o.Order_ID.split('-').pop(), // get order number
        shipping: o.Shipping_Cost_USD,
        exposure: riskExposure
      };
    });

    // 12. Penalty Exposure by Supplier
    const supPenalties = {};
    orders.forEach(o => {
      const sup = o.Supplier_ID;
      const penalty = o.Delay_Penalty_USD_Per_Day * 5 * o.Risk_Probability;
      supPenalties[sup] = (supPenalties[sup] || 0) + penalty;
    });
    const supplierPenalties = Object.keys(supPenalties).map(k => ({
      name: k,
      value: Math.round(supPenalties[k])
    })).sort((a,b) => b.value - a.value).slice(0, 5);

    return {
      riskBreakdown,
      featureImportance,
      samplesSplit,
      fwdHighRisk,
      fwdAvgRisk,
      fwdVolume,
      materialStock,
      complexityRisk,
      millMix,
      supplierExposure,
      topOrdersCost,
      supplierPenalties
    };
  };

  const analyticsData = getAnalyticsData();

  return (
    <div className="min-h-screen flex flex-col font-sans">
      
      {/* ── HEADER ── */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-brand-500/10 border border-brand-500/30 p-2 rounded-xl text-brand-400 shadow-glow animate-pulse-slow">
              <Scissors className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white font-outfit">ASBA Dashboard</h1>
              <p className="text-xs text-slate-400 font-light">Autonomous Supply Chain Bottleneck Agent &bull; Garment Logistics</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <span className="flex items-center text-xs font-medium text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-3 py-1 rounded-full">
              <span className="w-2 h-2 rounded-full bg-emerald-400 mr-2 animate-ping"></span>
              Agent Active
            </span>
          </div>
        </div>
      </header>

      {/* ── MAIN LAYOUT ── */}
      <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col space-y-6">
        
        {/* ── NAVIGATION TABS ── */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-2 space-y-4 sm:space-y-0">
          <div className="flex space-x-2">
            <button
              onClick={() => { setActiveTab('today'); setExpandedOrder(null); }}
              className={`px-5 py-2.5 rounded-lg text-sm font-semibold tracking-wide transition-all ${
                activeTab === 'today'
                  ? 'bg-brand-500 text-white shadow-glow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900/50'
              }`}
            >
              <Activity className="w-4 h-4 inline mr-2" />
              Sourcing Risks
            </button>
            <button
              onClick={() => { setActiveTab('analytics'); setExpandedOrder(null); }}
              className={`px-5 py-2.5 rounded-lg text-sm font-semibold tracking-wide transition-all ${
                activeTab === 'analytics'
                  ? 'bg-brand-500 text-white shadow-glow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900/50'
              }`}
            >
              <TrendingUp className="w-4 h-4 inline mr-2" />
              Analytics & Infographics
            </button>
            <button
              onClick={() => { setActiveTab('history'); setExpandedOrder(null); fetchHistory(); }}
              className={`px-5 py-2.5 rounded-lg text-sm font-semibold tracking-wide transition-all ${
                activeTab === 'history'
                  ? 'bg-brand-500 text-white shadow-glow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900/50'
              }`}
            >
              <History className="w-4 h-4 inline mr-2" />
              Historical Runs
            </button>
            <button
              onClick={() => { setActiveTab('chat'); setExpandedOrder(null); }}
              className={`px-5 py-2.5 rounded-lg text-sm font-semibold tracking-wide transition-all ${
                activeTab === 'chat'
                  ? 'bg-brand-500 text-white shadow-glow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900/50'
              }`}
            >
              <MessageSquare className="w-4 h-4 inline mr-2" />
              Agent Chat
            </button>
          </div>

          {(activeTab === 'history' || activeTab === 'analytics') && (
            <div className="flex items-center space-x-3 bg-slate-900/80 border border-slate-800 p-1.5 rounded-lg">
              <span className="text-xs text-slate-400 font-medium px-2"><Calendar className="w-3.5 h-3.5 inline mr-1 text-brand-400" /> Select Run:</span>
              <select
                value={selectedHistIndex}
                onChange={(e) => {
                  const idx = parseInt(e.target.value);
                  setSelectedHistIndex(idx);
                  setExpandedOrder(null);
                  if (idx !== -1 && history[idx]) {
                    setPredictionData(history[idx].data);
                  }
                }}
                className="bg-slate-950 border border-slate-850 text-sm rounded px-3 py-1.5 text-white outline-none focus:border-brand-500"
              >
                {history.length === 0 ? (
                  <option value="-1">No historical logs</option>
                ) : (
                  history.map((run, idx) => (
                    <option key={idx} value={idx}>
                      {run.date.slice(0,4)}-{run.date.slice(4,6)}-{run.date.slice(6,8)} ({run.balancing_method})
                    </option>
                  ))
                )}
              </select>
            </div>
          )}
        </div>

        {/* ── ERROR DISPLAY ── */}
        {error && (
          <div className="bg-red-950/20 border border-red-500/30 p-4 rounded-xl flex items-start space-x-3 text-red-200">
            <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-grow">
              <h4 className="font-bold text-sm">Execution Error</h4>
              <p className="text-xs mt-1 text-red-300/90 leading-relaxed">{error}</p>
            </div>
            <button onClick={() => setError(null)} className="text-xs text-slate-400 hover:text-white font-bold">&times;</button>
          </div>
        )}

        {/* ── LOADING SCREEN ── */}
        {loading && (
          <div className="glass-panel-heavy rounded-2xl p-12 text-center flex flex-col items-center justify-center space-y-6 shadow-glow border-brand-500/10 min-h-[450px]">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-slate-800 border-t-brand-500 rounded-full animate-spin"></div>
              <Sparkles className="w-6 h-6 text-brand-400 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
            </div>
            <div className="space-y-2 max-w-lg">
              <h3 className="text-lg font-bold font-outfit text-white">ASBA Agent Pipeline Executing</h3>
              <p className="text-slate-400 text-xs">This executes data generation, synthetically balances the 2000-row logistics dataset, trains an XGBoost classifier, and runs the Gemini reasoning loop.</p>
            </div>
            
            {/* Step Progress */}
            <div className="w-full max-w-md bg-slate-900 border border-slate-800/80 p-5 rounded-xl text-left space-y-3">
              <span className="text-[10px] uppercase font-bold tracking-widest text-slate-500">Pipeline logs:</span>
              <div className="space-y-2.5">
                {loadingSteps.map((step, idx) => (
                  <div key={idx} className="flex items-start text-xs space-x-2.5">
                    {loadingStep > idx ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                    ) : loadingStep === idx ? (
                      <RefreshCw className="w-4 h-4 text-brand-400 animate-spin flex-shrink-0 mt-0.5" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-slate-700 flex-shrink-0 mt-0.5"></div>
                    )}
                    <span className={loadingStep === idx ? "text-white font-medium" : loadingStep > idx ? "text-slate-400" : "text-slate-600"}>
                      {step}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── TODAY TAB WELCOME / RUN PROMPT ── */}
        {!loading && activeTab === 'today' && !predictionData && (
          <div className="glass-panel rounded-2xl p-12 text-center max-w-3xl mx-auto flex flex-col items-center space-y-6 card-hover">
            <div className="bg-brand-500/10 p-4 rounded-full text-brand-400 shadow-glow">
              <Database className="w-10 h-10" />
            </div>
            <div className="space-y-2 max-w-xl">
              <h2 className="text-2xl font-bold font-outfit text-white">Trigger Today's Risk Assessment</h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                Clicking the button below will spawn a Node.js/Python microservice to generate 2000 rows of specialized garment manufacturing logistics data, balance class imbalance using SMOTE or CTGAN, train a predictive model, and analyze the results using Google Gemini AI.
              </p>
            </div>
            <button
              onClick={runPrediction}
              className="bg-brand-500 hover:bg-brand-600 text-white font-semibold py-3 px-8 rounded-xl shadow-glow transition-all flex items-center space-x-2 text-sm tracking-wider"
            >
              <Play className="w-4 h-4 fill-white" />
              <span>GENERATE RISK ASSESSMENT PREDICTION</span>
            </button>
          </div>
        )}

        {/* ── HISTORY TAB EMPTY STATE ── */}
        {!loading && activeTab === 'history' && history.length === 0 && (
          <div className="glass-panel rounded-2xl p-12 text-center max-w-2xl mx-auto flex flex-col items-center space-y-4">
            <AlertTriangle className="w-10 h-10 text-amber-500" />
            <h2 className="text-xl font-bold font-outfit text-white">No Historical Runs Found</h2>
            <p className="text-slate-400 text-sm max-w-md">
              Please go to the "Today's Assessment" tab and generate a new prediction run first. Reports will be saved locally and list here.
            </p>
          </div>
        )}

        {/* ── AGENT CHAT TAB ── */}
        {!loading && activeTab === 'chat' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-[500px]">
            {/* Left side: Context details */}
            <div className="lg:col-span-1 space-y-4">
              <div className="glass-panel p-5 rounded-2xl space-y-3">
                <h3 className="text-sm font-bold text-white font-outfit">Sourcing Context</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  You are chatting with the <strong>Sourcing Mitigation Specialist Agent</strong>. 
                  You can query alternative suppliers for specific material groups:
                </p>
                <div className="space-y-2 pt-2">
                  <div className="p-2.5 bg-slate-900/60 border border-slate-800 rounded-lg text-xs space-y-1">
                    <span className="font-semibold text-brand-400 block">Fabric Alternatives</span>
                    <span className="text-slate-400 font-light">"Show me alternative suppliers for Fabric_Body"</span>
                  </div>
                  <div className="p-2.5 bg-slate-900/60 border border-slate-800 rounded-lg text-xs space-y-1">
                    <span className="font-semibold text-brand-400 block">Thread Shortages</span>
                    <span className="text-slate-400 font-light">"Who can supply Threads?"</span>
                  </div>
                  <div className="p-2.5 bg-slate-900/60 border border-slate-800 rounded-lg text-xs space-y-1">
                    <span className="font-semibold text-brand-400 block">Sewing Trims bottlenecks</span>
                    <span className="text-slate-400 font-light">"Look up alternative partners for Sewing_Trims"</span>
                  </div>
                </div>
              </div>

              {chatReasoning.length > 0 && (
                <div className="glass-panel p-5 rounded-2xl space-y-2 max-h-[250px] overflow-y-auto">
                  <h4 className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Agent Thinking Process</h4>
                  <div className="space-y-1">
                    {chatReasoning.map((step, idx) => (
                      <div key={idx} className="text-[10px] font-mono text-slate-400 leading-normal border-l-2 border-brand-500/30 pl-2">
                        {step}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Right side: Interactive Chat Console */}
            <div className="lg:col-span-2 glass-panel rounded-2xl flex flex-col h-[550px] overflow-hidden">
              <div className="p-4 border-b border-slate-800 bg-slate-900/40 flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className="w-2.5 h-2.5 bg-emerald-400 rounded-full animate-ping"></div>
                  <span className="text-xs font-bold text-white uppercase tracking-wider">Sourcing Specialist Chat Console</span>
                </div>
                <button
                  onClick={() => {
                    setChatMessages([{
                      role: 'assistant',
                      text: "Hello! I am your AI Sourcing Mitigation Specialist. How can I help you resolve today's garment supply chain bottlenecks?"
                    }]);
                    setChatReasoning([]);
                  }}
                  className="text-[10px] font-semibold text-slate-400 hover:text-white uppercase transition-all"
                >
                  Clear History
                </button>
              </div>

              {/* Message Feed */}
              <div className="flex-grow p-4 overflow-y-auto space-y-3.5 flex flex-col">
                {chatMessages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`max-w-[75%] p-3 rounded-xl text-xs leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-brand-600 text-white self-end rounded-br-none'
                        : 'bg-slate-900/80 border border-slate-800 text-slate-200 self-start rounded-bl-none'
                    }`}
                  >
                    {msg.text}
                  </div>
                ))}
                {chatLoading && (
                  <div className="bg-slate-900/80 border border-slate-800 text-slate-400 self-start rounded-xl rounded-bl-none p-3 max-w-[75%] text-xs flex items-center space-x-2">
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    <span className="italic ml-1 text-slate-450">Agent is searching directory & reasoning...</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Input Panel */}
              <div className="p-3 border-t border-slate-800 bg-slate-900/20 flex space-x-2 items-center">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleSendChatMessage(); }}
                  placeholder="Ask the mitigator about alternatives for Fabric_Body, Threads, Sewing_Trims..."
                  className="flex-grow bg-slate-950 border border-slate-850 rounded-xl px-4 py-2.5 text-xs text-white outline-none focus:border-brand-500 placeholder-slate-500"
                  disabled={chatLoading}
                />
                <button
                  onClick={handleSendChatMessage}
                  disabled={chatLoading || !chatInput.trim()}
                  className="bg-brand-500 hover:bg-brand-600 disabled:bg-slate-800 disabled:text-slate-500 text-white font-semibold px-4 py-2.5 rounded-xl text-xs tracking-wider transition-all"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── DASHBOARD RESULTS (KPIs, Charts, Table) ── */}
        {!loading && data && (
          <div className="space-y-6">
            
            {/* KPI Cards Row */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="glass-panel p-5 rounded-2xl flex items-center space-x-4 card-hover">
                <div className="p-3 bg-brand-500/10 text-brand-400 rounded-xl">
                  <Award className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs text-slate-400 font-medium block">Model Accuracy</span>
                  <span className="text-xl font-bold text-white">{(data.metrics?.accuracy * 100).toFixed(1)}%</span>
                </div>
              </div>
              
              <div className="glass-panel p-5 rounded-2xl flex items-center space-x-4 card-hover">
                <div className="p-3 bg-brand-500/10 text-brand-400 rounded-xl">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs text-slate-400 font-medium block">Model F1-Score</span>
                  <span className="text-xl font-bold text-white">{(data.metrics?.f1_score * 100).toFixed(1)}%</span>
                </div>
              </div>
              
              <div className="glass-panel p-5 rounded-2xl flex items-center space-x-4 card-hover">
                <div className="p-3 bg-red-500/10 text-red-400 rounded-xl">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs text-slate-400 font-medium block">High Risk Orders</span>
                  <span className="text-xl font-bold text-red-500">{data.predictions_summary?.high_risk_count || 0} <span className="text-xs text-slate-500 font-normal">/ {data.predictions_summary?.total_current_orders || 0}</span></span>
                </div>
              </div>
              
              <div className="glass-panel p-5 rounded-2xl flex items-center space-x-4 card-hover">
                <div className="p-3 bg-brand-500/10 text-brand-400 rounded-xl">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs text-slate-400 font-medium block">Balancing Strategy</span>
                  <span className="text-xl font-bold text-white">{data.metrics?.balancing_method || 'SMOTE'}</span>
                </div>
              </div>
            </div>

            {/* ── CHARTS / DETAILS CONDITIONAL VIEW ── */}
            {activeTab === 'analytics' ? (
              <div className="space-y-12">
                
                {/* ── CATEGORY A: SOURCING & MATERIAL RISKS ── */}
                <div className="space-y-4">
                  <div className="border-b border-slate-800 pb-2">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider font-outfit">Category A: Sourcing & Material Risks</h3>
                    <p className="text-xs text-slate-400">Analysis of raw material stockouts, production complexity, and predictive features driving manufacturing delay risk.</p>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    
                    {/* Chart 1: Risk Distribution Donut */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">1. Risk Level Distribution</h4>
                      <div className="flex-grow relative flex items-center justify-center">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={analyticsData?.riskBreakdown || []}
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={85}
                              paddingAngle={5}
                              dataKey="value"
                            >
                              {(analyticsData?.riskBreakdown || []).map((entry, index) => {
                                const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'];
                                return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                              })}
                            </Pie>
                            <Tooltip 
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 2: Top Feature Importance */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">2. Top Risk Factor Importances (XGBoost)</h4>
                      <div className="flex-grow">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analyticsData?.featureImportance || []} layout="vertical" margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis type="number" stroke="#94a3b8" fontSize={9} />
                            <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={9} width={90} />
                            <Tooltip
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Bar dataKey="value" name="Importance Score" fill="#10b981" radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 3: Stock Levels vs Delay Risk */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">3. Stock Levels vs Delay Risk</h4>
                      <div className="flex-grow">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analyticsData?.materialStock || []} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} />
                            <YAxis stroke="#94a3b8" fontSize={10} />
                            <Tooltip
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                            <Bar dataKey="Safe" name="Safe Orders Avg Stock" fill="#10b981" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="HighRisk" name="Delayed Orders Avg Stock" fill="#ef4444" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 4: Color Complexity vs Risk */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">4. Color Complexity vs Delay Risk</h4>
                      <div className="flex-grow">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={analyticsData?.complexityRisk || []} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} />
                            <YAxis stroke="#94a3b8" fontSize={10} tickFormatter={(val) => `${Math.round(val * 100)}%`} />
                            <Tooltip
                              formatter={(value) => [`${(value * 100).toFixed(1)}%`, 'Average Risk Probability']}
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              labelStyle={{ color: '#94a3b8', fontWeight: 'bold' }}
                            />
                            <Line type="monotone" dataKey="risk" name="Avg Risk Probability" stroke="#f59e0b" strokeWidth={3} activeDot={{ r: 8 }} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                  </div>
                </div>

                {/* ── CATEGORY B: LOGISTICS & CARRIER BOTTLE-NECKS ── */}
                <div className="space-y-4">
                  <div className="border-b border-slate-800 pb-2">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider font-outfit">Category B: Logistics & Carrier Bottlenecks</h3>
                    <p className="text-xs text-slate-400">Logistics operations, forwarder congestion, shipping volume, and mill sourcing distribution.</p>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                    {/* Chart 5: High Risk Shipments by Carrier */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">5. High Risk Shipments by Carrier</h4>
                      <div className="flex-grow">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analyticsData?.fwdHighRisk || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} />
                            <YAxis stroke="#94a3b8" fontSize={10} allowDecimals={false} />
                            <Tooltip
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Bar dataKey="count" name="High Risk Orders" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 6: Average Delay Risk by Carrier */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">6. Average Delay Risk by Carrier</h4>
                      <div className="flex-grow">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analyticsData?.fwdAvgRisk || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} />
                            <YAxis stroke="#94a3b8" fontSize={10} tickFormatter={(val) => `${Math.round(val * 100)}%`} />
                            <Tooltip
                              formatter={(value) => [`${(value * 100).toFixed(1)}%`, 'Average Risk Probability']}
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              labelStyle={{ color: '#94a3b8', fontWeight: 'bold' }}
                            />
                            <Bar dataKey="risk" name="Avg Risk Probability" fill="#0ea0ea" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 7: Cargo Volume Distributed by Carrier */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">7. Cargo Volume Distributed by Carrier</h4>
                      <div className="flex-grow relative flex items-center justify-center">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={analyticsData?.fwdVolume || []}
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={85}
                              paddingAngle={5}
                              dataKey="value"
                            >
                              {(analyticsData?.fwdVolume || []).map((entry, index) => {
                                const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6'];
                                return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                              })}
                            </Pie>
                            <Tooltip 
                              formatter={(val) => [`${val.toLocaleString()} units`, 'Shipping Volume']}
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 8: Mill Sourcing Mix */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">8. Mill Sourcing Mix (Active Shipments)</h4>
                      <div className="flex-grow relative flex items-center justify-center">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={analyticsData?.millMix || []}
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={85}
                              paddingAngle={5}
                              dataKey="value"
                            >
                              {(analyticsData?.millMix || []).map((entry, index) => {
                                const colors = ['#10b981', '#3b82f6', '#8b5cf6'];
                                return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                              })}
                            </Pie>
                            <Tooltip 
                              formatter={(val) => [`${val} Orders`, 'Order count']}
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                  </div>
                </div>

                {/* ── CATEGORY C: FINANCIAL EXPOSURE & VALIDATION METRICS ── */}
                <div className="space-y-4">
                  <div className="border-b border-slate-800 pb-2">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider font-outfit">Category C: Financial Exposure & Validation Metrics</h3>
                    <p className="text-xs text-slate-400">Active exposure assessments, expected contract penalty values, order margins, and model verification.</p>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                    {/* Chart 9: Value at Risk (VaR) by Supplier */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">9. Value at Risk (VaR) by Supplier</h4>
                      <div className="flex-grow">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analyticsData?.supplierExposure || []} layout="vertical" margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis type="number" stroke="#94a3b8" fontSize={9} tickFormatter={(val) => `$${val}`} />
                            <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={9} width={90} />
                            <Tooltip
                              formatter={(val) => [`$${val.toLocaleString()}`, 'Value at Risk']}
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Bar dataKey="value" name="Value at Risk (USD)" fill="#ef4444" radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 10: Contract Penalty Risk by Supplier */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">10. Penalty Exposure by Supplier</h4>
                      <div className="flex-grow">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analyticsData?.supplierPenalties || []} layout="vertical" margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis type="number" stroke="#94a3b8" fontSize={9} tickFormatter={(val) => `$${val}`} />
                            <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={9} width={90} />
                            <Tooltip
                              formatter={(val) => [`$${val.toLocaleString()}`, 'Penalty Risk Exposure']}
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Bar dataKey="value" name="Expected Delay Penalties" fill="#f59e0b" radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 11: Top 5 Orders Shipping Cost vs Risk Exposure */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">11. Top 5 Orders Shipping Cost vs Risk Exposure</h4>
                      <div className="flex-grow">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analyticsData?.topOrdersCost || []} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} tickFormatter={(val) => `Order ${val}`} />
                            <YAxis stroke="#94a3b8" fontSize={10} tickFormatter={(val) => `$${val}`} />
                            <Tooltip
                              formatter={(value) => [`$${value.toLocaleString()}`, value === 'shipping' ? 'Shipping Cost' : 'Risk Exposure']}
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              labelStyle={{ color: '#94a3b8', fontWeight: 'bold' }}
                            />
                            <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                            <Bar dataKey="shipping" name="Base Shipping Cost" stackId="topCost" fill="#3b82f6" />
                            <Bar dataKey="exposure" name="Expected Penalty Risk" stackId="topCost" fill="#ef4444" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Chart 12: Train/Test Validation Split */}
                    <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">12. XGBoost ML Validation Dataset Split</h4>
                      <div className="flex-grow relative flex items-center justify-center">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={analyticsData?.samplesSplit || []}
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={85}
                              paddingAngle={5}
                              dataKey="count"
                            >
                              {(analyticsData?.samplesSplit || []).map((entry, index) => {
                                const colors = ['#8b5cf6', '#3b82f6'];
                                return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                              })}
                            </Pie>
                            <Tooltip 
                              formatter={(val) => [`${val.toLocaleString()} rows`, 'Samples']}
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                              itemStyle={{ color: '#fff' }}
                            />
                            <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                  </div>
                </div>

              </div>
            ) : (
              <>
                {/* ── 3 STANDARD SUMMARY CHARTS ── */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  
                  {/* Risk Distribution Donut */}
                  <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Risk Distribution</h3>
                    <div className="flex-grow relative flex items-center justify-center">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={pieData}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={85}
                            paddingAngle={5}
                            dataKey="value"
                          >
                            {pieData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                            itemStyle={{ color: '#fff' }}
                          />
                          <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Forwarder Bottleneck */}
                  <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Bottleneck by Forwarder</h3>
                    <div className="flex-grow">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={forwarderData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="forwarder" stroke="#94a3b8" fontSize={11} />
                          <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                            labelStyle={{ color: '#94a3b8', fontWeight: 'bold' }}
                            itemStyle={{ color: '#fff' }}
                          />
                          <Bar dataKey="high_risk_count" name="High Risk Orders" fill="#0ea0ea" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Material Bottleneck */}
                  <div className="glass-panel p-5 rounded-2xl flex flex-col h-[320px]">
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Top Feature Importances (Material Risks)</h3>
                    <div className="flex-grow">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={materialData} layout="vertical" margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis type="number" stroke="#94a3b8" fontSize={11} />
                          <YAxis dataKey="material" type="category" stroke="#94a3b8" fontSize={10} width={100} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                            itemStyle={{ color: '#fff' }}
                          />
                          <Bar dataKey="correlation" name="Importance Score" fill="#10b981" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                </div>

                {/* ── HIGH RISK ORDERS TABLE ── */}
                <div className="glass-panel rounded-2xl overflow-hidden">
                  <div className="p-5 border-b border-slate-800 flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-white font-outfit">High-Risk Orders Assessment</h3>
                      <p className="text-xs text-slate-400 mt-1">Orders flagged with late delivery probability &gt; 70% requiring manual check or remediation.</p>
                    </div>
                    {activeTab === 'today' && (
                      <button
                        onClick={runPrediction}
                        className="bg-slate-900 border border-slate-850 hover:bg-slate-800 text-xs font-bold py-1.5 px-3 rounded-lg text-slate-300 hover:text-white transition-all flex items-center space-x-1.5"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        <span>Re-Run</span>
                      </button>
                    )}
                  </div>

                  {data.high_risk_orders?.length === 0 ? (
                    <div className="p-10 text-center text-slate-400 text-sm">
                      <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                      No high risk orders detected for today's run. All shipments are assessed as on-time.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm border-collapse">
                        <thead>
                          <tr className="bg-slate-900/60 border-b border-slate-850 text-slate-400 text-xs font-semibold uppercase tracking-wider">
                            <th className="p-4 w-10"></th>
                            <th className="p-4">Order ID</th>
                            <th className="p-4">Supplier</th>
                            <th className="p-4">Priority</th>
                            <th className="p-4">Forwarder</th>
                            <th className="p-4 text-center">Risk Level</th>
                            <th className="p-4 text-right">Probability</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.high_risk_orders?.map((order, idx) => {
                            const isExpanded = expandedOrder === idx;
                            return (
                              <React.Fragment key={idx}>
                                <tr 
                                  onClick={() => setExpandedOrder(isExpanded ? null : idx)}
                                  className="border-b border-slate-850 hover:bg-slate-900/40 transition-colors cursor-pointer"
                                >
                                  <td className="p-4 text-center text-slate-400">
                                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                  </td>
                                  <td className="p-4 font-semibold text-white">{order.Order_ID}</td>
                                  <td className="p-4 text-slate-300">{order.Supplier_ID}</td>
                                  <td className="p-4">
                                    <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                      order.Order_Priority === 'Critical' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                                      order.Order_Priority === 'High' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                                      order.Order_Priority === 'Medium' ? 'bg-brand-500/10 text-brand-400 border border-brand-500/20' :
                                      'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                                    }`}>
                                      {order.Order_Priority}
                                    </span>
                                  </td>
                                  <td className="p-4 text-slate-300">
                                    <span className="flex items-center">
                                      <Truck className="w-3.5 h-3.5 text-slate-500 mr-1.5" />
                                      {order.Forwarder}
                                    </span>
                                  </td>
                                  <td className="p-4 text-center">
                                    <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                      order.Risk_Level === 'CRITICAL' ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
                                      'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                    }`}>
                                      {order.Risk_Level}
                                    </span>
                                  </td>
                                  <td className="p-4 text-right font-bold text-brand-400">{(order.Risk_Probability * 100).toFixed(1)}%</td>
                                </tr>
                                {isExpanded && (
                                  <tr className="bg-slate-900/30">
                                    <td colspan="7" className="p-6 border-b border-slate-850">
                                      <div className="space-y-6">
                                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                                          
                                          {/* Order Details list */}
                                          <div className="bg-slate-950/80 border border-slate-850 p-4 rounded-xl space-y-3">
                                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center">
                                              <Database className="w-3.5 h-3.5 text-brand-400 mr-1.5" /> Features Analysis
                                            </h4>
                                            <div className="grid grid-cols-2 gap-y-2.5 gap-x-4 text-xs">
                                              <div>
                                                <span className="text-slate-500 block">Fabric Body</span>
                                                <span className="text-white font-medium">{order.Fabric_Body}m</span>
                                              </div>
                                              <div>
                                                <span className="text-slate-500 block">Color Sets</span>
                                                <span className="text-white font-medium">{order.Color_Sets_Count} sets</span>
                                              </div>
                                              <div>
                                                <span className="text-slate-500 block">Mill Source</span>
                                                <span className="text-white font-medium">{order.Mill_Source} Mill</span>
                                              </div>
                                              <div>
                                                <span className="text-slate-500 block">Threads</span>
                                                <span className="text-white font-medium">{order.Threads}m</span>
                                              </div>
                                              <div>
                                                <span className="text-slate-500 block">Sewing Trims</span>
                                                <span className="text-white font-medium">{order.Sewing_Trims} pcs</span>
                                              </div>
                                              <div>
                                                <span className="text-slate-500 block">Packing Trims</span>
                                                <span className="text-white font-medium">{order.Packing_Trims} pcs</span>
                                              </div>
                                            </div>
                                          </div>

                                          {/* Gemini Remediation Advice */}
                                          <div className="bg-brand-500/[0.02] border border-brand-500/10 p-5 rounded-xl space-y-3 flex flex-col justify-between">
                                            <div>
                                              <h4 className="text-xs font-bold text-brand-400 uppercase tracking-widest flex items-center">
                                                 <Sparkles className="w-3.5 h-3.5 text-brand-400 mr-1.5" /> Gemini Remediation
                                               </h4>
                                               <p className="text-slate-300 text-xs mt-2.5 leading-relaxed font-light">
                                                 {order.remediation_advice}
                                               </p>
                                             </div>
                                             <div className="text-[10px] text-slate-500 border-t border-slate-850 pt-2.5 flex items-center justify-between">
                                               <span>Generative recommendations compiled</span>
                                               <span className="text-brand-500/80 font-medium">Model: gemini-2.5-flash</span>
                                             </div>
                                           </div>

                                           {/* Agentic Sourcing Mitigation Panel */}
                                           <div className="bg-slate-900/60 border border-slate-850 p-5 rounded-xl space-y-4 flex flex-col justify-between">
                                             <div>
                                               <h4 className="text-xs font-bold text-white uppercase tracking-widest flex items-center">
                                                 <Activity className="w-3.5 h-3.5 text-brand-400 mr-1.5" /> Sourcing Action
                                               </h4>
                                               
                                               {order.mitigated ? (
                                                 <div className="mt-4 bg-emerald-950/25 border border-emerald-500/20 p-4 rounded-xl flex flex-col items-center justify-center text-center space-y-2">
                                                   <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                                                   <span className="text-xs font-bold text-white">Mitigation Applied</span>
                                                   <span className="text-[10px] text-emerald-300 leading-normal">{order.mitigation_action}</span>
                                                 </div>
                                               ) : (
                                                 <div className="space-y-3 mt-3">
                                                   <div>
                                                     <label className="text-[10px] text-slate-500 font-bold block mb-1">Select Action</label>
                                                     <select
                                                       value={mitigationChoices[order.Order_ID] || 'logistics'}
                                                       onChange={(e) => setMitigationChoices(prev => ({ ...prev, [order.Order_ID]: e.target.value }))}
                                                       className="w-full bg-slate-950 border border-slate-850 text-xs rounded p-2 text-white outline-none focus:border-brand-500"
                                                     >
                                                       <option value="logistics">Upgrade Carrier to DHL (Express)</option>
                                                       <option value="mill">Switch Mill to Internal Source</option>
                                                       <option value="supplier">Re-assign to B2B Partner</option>
                                                     </select>
                                                   </div>

                                                   {(mitigationChoices[order.Order_ID] === 'supplier') && (
                                                     <div>
                                                       <label className="text-[10px] text-slate-500 font-bold block mb-1">Select B2B Alternative</label>
                                                       <select
                                                         value={selectedSuppliers[order.Order_ID] || getAltsForOrder(order)[0]?.id}
                                                         onChange={(e) => setSelectedSuppliers(prev => ({ ...prev, [order.Order_ID]: e.target.value }))}
                                                         className="w-full bg-slate-950 border border-slate-850 text-xs rounded p-2 text-white outline-none focus:border-brand-500"
                                                       >
                                                         {getAltsForOrder(order).map(alt => (
                                                           <option key={alt.id} value={alt.id}>
                                                             {alt.name}
                                                           </option>
                                                         ))}
                                                       </select>
                                                     </div>
                                                   )}

                                                   <button
                                                     onClick={() => handleMitigate(order.Order_ID)}
                                                     disabled={mitigationLoading[order.Order_ID]}
                                                     className="w-full mt-2 bg-brand-500 hover:bg-brand-600 disabled:bg-slate-800 text-white font-bold py-2 px-4 rounded text-xs transition-all flex items-center justify-center space-x-1.5 shadow-glow"
                                                   >
                                                     {mitigationLoading[order.Order_ID] ? (
                                                       <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                                     ) : (
                                                       <>
                                                         <Play className="w-3 h-3 fill-white" />
                                                         <span>Execute Sourcing Plan</span>
                                                       </>
                                                     )}
                                                   </button>
                                                 </div>
                                               )}
                                             </div>
                                             
                                             <div className="text-[10px] text-slate-500 border-t border-slate-850 pt-2 flex items-center justify-between">
                                               <span>Updates active csv & recalculates ML risk</span>
                                             </div>
                                           </div>
                                         </div>

                                         {/* Stacked Cost-Benefit Comparison Chart */}
                                         {!order.mitigated && (
                                           <div className="glass-panel p-5 bg-slate-950/40 border border-slate-850 rounded-xl space-y-4">
                                             <div className="flex items-center justify-between border-b border-slate-850 pb-2">
                                               <h4 className="text-xs font-bold text-slate-300 uppercase tracking-widest flex items-center">
                                                 <TrendingUp className="w-3.5 h-3.5 text-brand-400 mr-1.5" /> Sourcing Cost & Risk Exposure Comparison
                                               </h4>
                                               <span className="text-[10px] text-slate-400 font-light">Total Cost = Shipping + Sourcing Premium + Expected Late Penalty</span>
                                             </div>
                                             <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-center">
                                               <div className="lg:col-span-3 h-[200px]">
                                                 <ResponsiveContainer width="100%" height="100%">
                                                   <BarChart data={calculateLocalCosts(order)} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                                                     <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                                     <XAxis dataKey="name" stroke="#94a3b8" fontSize={9} />
                                                     <YAxis stroke="#94a3b8" fontSize={9} tickFormatter={(val) => `$${val}`} />
                                                     <Tooltip
                                                       formatter={(value, name) => [`$${value}`, name === 'shipping' ? 'Shipping Cost' : name === 'premium' ? 'Sourcing Premium' : 'Risk Exposure']}
                                                       contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                                                       labelStyle={{ color: '#94a3b8', fontWeight: 'bold' }}
                                                     />
                                                     <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                                                     <Bar dataKey="shipping" name="Shipping Cost" stackId="cost" fill="#3b82f6" />
                                                     <Bar dataKey="premium" name="Sourcing Premium" stackId="cost" fill="#f59e0b" />
                                                     <Bar dataKey="exposure" name="Expected Penalty Risk" stackId="cost" fill="#ef4444" radius={[4, 4, 0, 0]} />
                                                   </BarChart>
                                                 </ResponsiveContainer>
                                               </div>
                                               <div className="bg-slate-950/80 border border-slate-850 p-4 rounded-lg space-y-2.5">
                                                 <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Mitigation Summary</span>
                                                 {(() => {
                                                   const costs = calculateLocalCosts(order);
                                                   const orig = costs[0];
                                                   const best = [...costs].sort((a, b) => a.total - b.total)[0];
                                                   return (
                                                     <div className="text-xs space-y-2 text-slate-300">
                                                       <div>
                                                         <span className="text-slate-500 block text-[10px]">Current Total Cost (Risk-Adjusted):</span>
                                                         <span className="font-bold text-red-400">${orig.total.toLocaleString()}</span>
                                                       </div>
                                                       <div>
                                                         <span className="text-slate-500 block text-[10px]">Recommended Action:</span>
                                                         <span className="font-bold text-emerald-400">{best.name}</span>
                                                       </div>
                                                       <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-850 leading-relaxed">
                                                         {best.name === 'Original Sourcing' ? (
                                                           <span>Proceed with current path. Mitigation premiums exceed delay penalty risks.</span>
                                                         ) : (
                                                           <span>Upgrading to <strong>{best.name}</strong> will save approx. <strong className="text-emerald-400">${(orig.total - best.total).toLocaleString()}</strong> in overall risk-adjusted cost.</span>
                                                         )}
                                                       </div>
                                                     </div>
                                                   );
                                                 })()}
                                               </div>
                                             </div>
                                           </div>
                                         )}
                                       </div>
                                     </td>
                                   </tr>
                                )}
                              </React.Fragment>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Reasoning Log Card */}
                <div className="glass-panel p-6 rounded-2xl space-y-3">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center">
                    <FileText className="w-4 h-4 text-brand-400 mr-1.5" /> Pipeline Reasoning Log
                  </h3>
                  <p className="text-slate-300 text-xs leading-relaxed font-light">
                    {data.reasoning_log || "No reasoning logs provided in this run."}
                  </p>
                  <div className="text-[10px] text-slate-500 flex items-center space-x-4 pt-1.5">
                    <span>Total training samples: {data.data_integrity?.total_rows} rows</span>
                    <span>&bull;</span>
                    <span>Missing values check: {data.data_integrity?.missing_values || 0}</span>
                    <span>&bull;</span>
                    <span>Minority ratio before balancing: {((data.data_integrity?.class_distribution_before?.Late / data.data_integrity?.total_rows) * 100 || 7.5).toFixed(1)}%</span>
                  </div>
                </div>
              </>
            )}

          </div>
        )}

      </main>

      {/* ── FOOTER ── */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          <p>&copy; 2026 Garment Manufacturing Company &bull; ASBA Autonomous Supply Chain Bottleneck Agent &bull; Powered by Google Gemini AI</p>
        </div>
      </footer>

    </div>
  );
}
