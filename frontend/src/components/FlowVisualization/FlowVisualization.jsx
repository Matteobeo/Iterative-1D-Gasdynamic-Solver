import React, { useRef, useEffect } from 'react';

export function FlowVisualization({ components, results }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!results || !results.data || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let animationFrameId;

    // Simulation data
    const { x, mach, pressure } = results.data;
    const totalL = x[x.length - 1];
    const maxP = Math.max(...pressure);
    const minP = Math.min(...pressure);

    // Particle system state
    const particles = [];
    const numParticles = 200;

    for (let i = 0; i < numParticles; i++) {
      particles.push({
        x: Math.random() * totalL,
        yOffset: (Math.random() - 0.5), // Normalized offset from centerline
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
      return 0.05;
    };

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;
      const margin = 40;
      const drawW = w - 2 * margin;
      const drawH = h - 2 * margin;

      ctx.clearRect(0, 0, w, h);

      // 1. Draw Background Duct with Velocity Color Map
      const steps = 100;
      for (let i = 0; i < steps; i++) {
        const x1 = (i / steps) * totalL;
        const x2 = ((i + 1) / steps) * totalL;
        const m = interpolate(x1, x, mach);
        const r1 = getDuctRadius(x1);
        const r2 = getDuctRadius(x2);

        // Color mapping: Blue (subsonic) -> Red (sonic) -> Purple (supersonic)
        let hue = 220; // Blue
        if (m < 1.0) {
          hue = 220 - (m * 180); // To Red
        } else {
          hue = 40 - (Math.min(m - 1, 1) * 40); // To Purple/Dark
        }
        
        ctx.fillStyle = `hsla(${hue}, 70%, 50%, 0.3)`;
        
        const px1 = margin + (x1 / totalL) * drawW;
        const px2 = margin + (x2 / totalL) * drawW;
        const py1_top = h / 2 - (r1 / 0.5) * (drawH / 2); // Normalized by 0.5m max radius
        const py1_bot = h / 2 + (r1 / 0.5) * (drawH / 2);
        const py2_top = h / 2 - (r2 / 0.5) * (drawH / 2);
        const py2_bot = h / 2 + (r2 / 0.5) * (drawH / 2);

        ctx.beginPath();
        ctx.moveTo(px1, py1_top);
        ctx.lineTo(px2, py2_top);
        ctx.lineTo(px2, py2_bot);
        ctx.lineTo(px1, py1_bot);
        ctx.closePath();
        ctx.fill();
      }

      // 2. Draw Particles (Density = Pressure)
      particles.forEach(p => {
        const m = interpolate(p.x, x, mach);
        const p_local = interpolate(p.x, x, pressure);
        const r = getDuctRadius(p.x);

        // Update position
        const speed = 0.005 + (m * 0.02);
        p.x += speed;
        if (p.x > totalL) p.x = 0;

        // Density visual trick: scale particle size/alpha by local pressure
        const p_norm = (p_local - minP) / (maxP - minP + 1e-6);
        const alpha = 0.2 + p_norm * 0.8;
        const size = 1 + p_norm * 2;

        const px = margin + (p.x / totalL) * drawW;
        const py = h / 2 + p.yOffset * (r / 0.5) * drawH;

        ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
        ctx.beginPath();
        ctx.arc(px, py, size, 0, Math.PI * 2);
        ctx.fill();
      });

      // 3. Draw Duct Outlines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i <= steps; i++) {
        const x_val = (i / steps) * totalL;
        const r = getDuctRadius(x_val);
        const px = margin + (x_val / totalL) * drawW;
        const py = h / 2 - (r / 0.5) * (drawH / 2);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.stroke();

      ctx.beginPath();
      for (let i = 0; i <= steps; i++) {
        const x_val = (i / steps) * totalL;
        const r = getDuctRadius(x_val);
        const px = margin + (x_val / totalL) * drawW;
        const py = h / 2 + (r / 0.5) * (drawH / 2);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.stroke();

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animationFrameId);
  }, [results, components]);

  return (
    <div className="glass-card animate-fade-in" style={{ marginTop: '1.5rem', overflow: 'hidden' }}>
      <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
        🌊 Dynamic Flow Visualization (Velocity Map & Pressure Particles)
      </div>
      <canvas 
        ref={canvasRef} 
        width={800} 
        height={200} 
        style={{ width: '100%', height: 'auto', display: 'block', background: 'rgba(0,0,0,0.2)' }}
      />
      <div style={{ padding: '0.5rem 1rem', fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
        <span>Inlet</span>
        <span>Color: Velocity (Blue=Sub, Red=Sonic, Purple=Sup) | Density: Local Pressure</span>
        <span>Exit</span>
      </div>
    </div>
  );
}
