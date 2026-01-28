// Sync error handling
try {
  JSON.parse("not-json");
} catch (e) {
  console.log("Sync error caught with try/catch:", e.message);
}

// Async error handling
async function run() {
  try {
    await Promise.reject(new Error("boom (async)"));
  } catch (e) {
    console.log("Async error caught with try/catch around await:", e.message);
  }
}

run();
