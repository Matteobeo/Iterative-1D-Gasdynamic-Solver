import React, { useRef, useEffect } from 'react';

export function FlowVisualization({ components, results }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!results || !results.data || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let animationFrameId;

    const { x, mach, pressure } = results.data;
    const totalL = x[x.length - 1];
    const maxP = Math.max(...pressure);
    const minP = Math.min(...pressure);

    // Calculate max radius for scaling
    let maxRadius = 0.01;
    components.forEach(c => {
      const r_in = (c.params.d_in || c.params.d_h || 0.1) / 2;
      const r_out = (c.params.d_out || c.params.d_h || 0.1) / 2;
      maxRadius = Math.max(maxRadius, r_in, r_out);
    });

    // Particle system state
    const particles = [];
    const numParticles = 250;
    for (let i = 0; i < numParticles; i++) {
      particles.push({
        x: Math.random() * totalL,
        yOffset: (Math.random() - 0.5) * 2, 
        life: Math.random()
      });
    }

    const interpolate = (val, xArr, yArr) => {
      if (val <= xArr[0]) return yArr[0];
      if (val >= xArr[xArr.length - 1]) return yArr[yArr.length - 1];
      let i = 0;
      while (i < xArr.length - 1 && xArr[i+1] < val) i++;
      const t = (val - xArr[i]) / (xArr[i+1] - xArr[i]);
      return yArr[i] + t * (yArr[i+1] - yArr[i]);
    };

    const getDuctRadius = (val) => {
      let currentX = 0;
      for (const comp of components) {
        const L = comp.params.length || 0;
        if (val >= currentX && val <= currentX + L) {
          const d_in = comp.params.d_in || comp.params.d_h || 0.1;
          const d_out = comp.params.d_out || comp.params.d_h || 0.1;
          const frac = L > 0 ? (val - currentX) / L : 0;
          return (d_in + (d_out - d_in) * frac) / 2;
        }
        currentX += L;
      }
      return maxRadius;
    };

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;
      const marginX = 60;
      const marginY = 30;
      const drawW = w - 2 * marginX;
      const drawH = h - 2 * marginY;

      ctx.clearRect(0, 0, w, h);

      // Scale factor to fit maxRadius into drawH/2
      const yScale = (drawH / 2) / maxRadius;

      // 1. Draw Background Duct with Velocity Gradient
      const steps = 150;
      for (let i = 0; i < steps; i++) {
        const x1 = (i / steps) * totalL;
        const x2 = ((i + 1) / steps) * totalL;
        const m = interpolate(x1, x, mach);
        const r1 = getDuctRadius(x1);
        const r2 = getDuctRadius(x2);

        const px1 = marginX + (x1 / totalL) * drawW;
        const px2 = marginX + (x2 / totalL) * drawW;
        const py1_t = h / 2 - r1 * yScale;
        const py1_b = h / 2 + r1 * yScale;
        const py2_t = h / 2 - r2 * yScale;
        const py2_b = h / 2 + r2 * yScale;

        let hue = 210; // Subsonic Blue
        let sat = 60;
        if (m < 1.0) {
            hue = 210 - (m * 180); // To Red
        } else {
            hue = 30 - (Math.min(m - 1, 1) * 30); // To Deep Red/Purple
            sat = 80;
        }
        
        ctx.fillStyle = `hsla(${hue}, ${sat}%, 45%, 0.25)`;
        ctx.beginPath();
        ctx.moveTo(px1, py1_t); ctx.lineTo(px2, py2_t);
        ctx.lineTo(px2, py2_b); ctx.lineTo(px1, py1_b);
        ctx.fill();

        // Subtle wall highlight
        ctx.strokeStyle = `hsla(${hue}, ${sat}%, 60%, 0.1)`;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(px1, py1_t); ctx.lineTo(px2, py2_t); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(px1, py1_b); ctx.lineTo(px2, py2_b); ctx.stroke();
      }

      // 2. Draw Particles (Density = Pressure, Velocity = Mach)
      ctx.shadowBlur = 4;
      particles.forEach(p => {
        const m = interpolate(p.x, x, mach);
        const p_local = interpolate(p.x, x, pressure);
        const r = getDuctRadius(p.x);

        p.x += 0.004 + (m * 0.015);
        if (p.x > totalL) {
            p.x = 0;
            p.yOffset = (Math.random() - 0.5) * 2;
        }

        const p_norm = (p_local - minP) / (maxP - minP + 1e-6);
        const alpha = 0.15 + p_norm * 0.6;
        const size = 0.8 + p_norm * 1.5;

        const px = marginX + (p.x / totalL) * drawW;
        const py = h / 2 + p.yOffset * r * yScale;

        ctx.shadowColor = 'white';
        ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
        ctx.beginPath();
        ctx.arc(px, py, size, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.shadowBlur = 0;

      // 3. Draw Outer Walls
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i <= steps; i++) {
        const xv = (i/steps) * totalL;
        const rv = getDuctRadius(xv);
        const px = marginX + (xv/totalL) * drawW;
        const py = h / 2 - rv * yScale;
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.stroke();

      ctx.beginPath();
      for (let i = 0; i <= steps; i++) {
        const xv = (i/steps) * totalL;
        const rv = getDuctRadius(xv);
        const px = marginX + (xv/totalL) * drawW;
        const py = h / 2 + rv * yScale;
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.stroke();

      animationFrameId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animationFrameId);
  }, [results, components]);

  return (
    <div className="glass-card animate-fade-in" style={{ marginTop: '2rem', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.15)' }}>
      <div style={{ padding: '0.75rem 1.25rem', background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          🌊 Dynamic Flow Simulation
        </span>
        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}><div style={{width:8, height:8, borderRadius:'50%', background:'#3b82f6'}}></div> Subsonic</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}><div style={{width:8, height:8, borderRadius:'50%', background:'#ef4444'}}></div> Sonic</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}><div style={{width:8, height:8, borderRadius:'50%', background:'#8b5cf6'}}></div> Supersonic</span>
        </div>
      </div>
      <canvas 
        ref={canvasRef} 
        width={1000} 
        height={250} 
        style={{ width: '100%', height: 'auto', display: 'block', background: 'radial-gradient(circle at center, #1e293b, #0f172a)' }}
      />
      <div style={{ padding: '0.6rem 1.25rem', fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', background: 'rgba(0,0,0,0.2)' }}>
        <span>INLET</span>
        <span style={{ fontStyle: 'italic', opacity: 0.8 }}>Particle Density $\propto$ Pressure | Particle Speed $\propto$ Mach Number</span>
        <span>EXIT</span>
      </div>
    </div>
  );
}
