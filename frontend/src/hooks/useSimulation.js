import { useState } from 'react';

export function useSimulation() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const simulate = async (config, components) => {
    setLoading(true);
    setError(null);
    setResults(null);
    
    try {
      const payload = {
        P0: parseFloat(config.P0),
        T0: parseFloat(config.T0),
        P_amb: parseFloat(config.P_amb),
        gamma: parseFloat(config.gamma),
        R: parseFloat(config.R),
        components: components.map(c => ({
          type: c.type,
          params: Object.fromEntries(
            Object.entries(c.params).map(([k, v]) => [k, parseFloat(v)])
          )
        })),
        solver_type: config.solver_type || "analytical"
      };

      const res = await fetch('http://localhost:8000/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Simulation failed");
      }
      
      setResults(data);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return { simulate, results, loading, error, clearResults: () => setResults(null) };
}
