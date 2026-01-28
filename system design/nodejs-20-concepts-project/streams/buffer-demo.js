// Buffer = raw bytes
const b = Buffer.from("Hi", "utf8");

console.log("Buffer:", b);
console.log("Buffer length (bytes):", b.length);
console.log("Back to string:", b.toString("utf8"));

// Example: bytes are not always printable
const raw = Buffer.from([0, 255, 16, 32]);
console.log("Raw bytes:", raw);
