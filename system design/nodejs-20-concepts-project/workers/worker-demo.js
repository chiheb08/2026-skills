import { Worker, isMainThread, parentPort, workerData } from "node:worker_threads";

function heavy(n) {
  let x = 0;
  for (let i = 0; i < n; i++) x += i % 7;
  return x;
}

if (isMainThread) {
  console.log("Main thread: starting CPU work in a worker thread...");

  const w = new Worker(new URL(import.meta.url), { workerData: { n: 60_000_000 } });
  w.on("message", (msg) => {
    console.log("Worker result:", msg);
  });
  w.on("error", (e) => console.error("Worker error:", e));
  w.on("exit", (code) => console.log("Worker exited with code", code));

  let ticks = 0;
  const interval = setInterval(() => {
    ticks++;
    console.log("Main thread tick", ticks);
    if (ticks >= 3) clearInterval(interval);
  }, 300);
} else {
  const result = heavy(workerData.n);
  parentPort.postMessage({ ok: true, result });
}
