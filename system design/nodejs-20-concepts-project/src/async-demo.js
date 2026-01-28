import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";

const filePath = path.join(process.cwd(), "data", "note.txt");

// Prepare a sample file (so the demo always works)
fs.mkdirSync(path.join(process.cwd(), "data"), { recursive: true });
fs.writeFileSync(filePath, "Hello from Node async demo!\n", "utf8");

console.log("\n--- Callback style ---");
fs.readFile(filePath, "utf8", (err, text) => {
  if (err) return console.error("Callback error:", err);
  console.log("Callback read:", text.trim());

  console.log("\n--- Promise style ---");
  fsp
    .readFile(filePath, "utf8")
    .then((t) => {
      console.log("Promise read:", t.trim());

      console.log("\n--- async/await style ---");
      return (async () => {
        const t2 = await fsp.readFile(filePath, "utf8");
        console.log("await read:", t2.trim());
      })();
    })
    .catch((e) => console.error("Promise error:", e));
});
