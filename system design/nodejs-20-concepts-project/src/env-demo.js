import "dotenv/config";

const port = process.env.PORT || "3000";
const nodeEnv = process.env.NODE_ENV || "development";

console.log("NODE_ENV:", nodeEnv);
console.log("PORT:", port);

console.log("\nTip: put secrets in env vars (or a secret manager), not in code.");
