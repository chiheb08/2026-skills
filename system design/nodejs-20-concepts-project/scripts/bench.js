// Tiny timing demo: shows why blocking work hurts.
const t0 = Date.now();

function heavy(n) {
  let x = 0;
  for (let i = 0; i < n; i++) x += i % 7;
  return x;
}

const result = heavy(80_000_000);
const ms = Date.now() - t0;

console.log("CPU work finished in", ms, "ms", "result:", result);
console.log("If this ran inside a request handler, every request would wait.");
