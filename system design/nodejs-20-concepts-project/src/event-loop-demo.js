console.log("1) Start");

setTimeout(() => {
  console.log("4) setTimeout callback (macrotask)");
}, 0);

Promise.resolve().then(() => {
  console.log("3) Promise.then callback (microtask)");
});

console.log("2) End (synchronous code finishes first)");
