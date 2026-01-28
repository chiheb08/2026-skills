import fs from "node:fs";
import path from "node:path";

// Create a "big" file (small enough for a demo)
const dataDir = path.join(process.cwd(), "data");
fs.mkdirSync(dataDir, { recursive: true });
const bigFile = path.join(dataDir, "big.txt");

if (!fs.existsSync(bigFile)) {
  const chunk = "hello stream\n";
  fs.writeFileSync(bigFile, chunk.repeat(200000), "utf8");
}

console.log("Reading big file using stream (chunk by chunk)...");

let bytes = 0;
const stream = fs.createReadStream(bigFile);
stream.on("data", (buf) => {
  bytes += buf.length;
});
stream.on("end", () => {
  console.log("Done. Total bytes:", bytes);
});
stream.on("error", (e) => console.error("Stream error:", e));
