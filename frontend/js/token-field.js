/**
 * Campo de puntos sutil: cada punto ≈ un token conceptual.
 * Movimiento casi imperceptible. Sin glow, sin neón.
 */

export function initTokenField(canvas) {
  if (!canvas) return () => {};

  const ctx = canvas.getContext('2d');
  let w = 0;
  let h = 0;
  let dots = [];
  let raf = 0;
  let running = true;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const density = Math.floor((w * h) / 14000);
    const n = Math.min(Math.max(density, 40), 160);
    dots = Array.from({ length: n }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 0.8 + 0.4,
      vx: (Math.random() - 0.5) * 0.08,
      vy: (Math.random() - 0.5) * 0.08,
      a: Math.random() * 0.25 + 0.08,
    }));
  }

  function frame() {
    if (!running) return;
    ctx.clearRect(0, 0, w, h);
    for (const d of dots) {
      d.x += d.vx;
      d.y += d.vy;
      if (d.x < 0) d.x = w;
      if (d.x > w) d.x = 0;
      if (d.y < 0) d.y = h;
      if (d.y > h) d.y = 0;
      ctx.beginPath();
      ctx.fillStyle = `rgba(138, 147, 166, ${d.a})`;
      ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
      ctx.fill();
    }
    raf = requestAnimationFrame(frame);
  }

  // Respeta preferencia de movimiento reducido
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reduce.matches) {
    resize();
    ctx.clearRect(0, 0, w, h);
    for (const d of dots) {
      ctx.beginPath();
      ctx.fillStyle = `rgba(138, 147, 166, ${d.a * 0.6})`;
      ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
      ctx.fill();
    }
    return () => {};
  }

  resize();
  frame();
  window.addEventListener('resize', resize);

  return () => {
    running = false;
    cancelAnimationFrame(raf);
    window.removeEventListener('resize', resize);
  };
}
