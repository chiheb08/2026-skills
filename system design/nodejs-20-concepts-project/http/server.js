import http from "node:http";
import url from "node:url";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const server = http.createServer(async (req, res) => {
  const parsed = url.parse(req.url, true);

  if (parsed.pathname === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  if (parsed.pathname === "/slow") {
    const ms = Number(parsed.query.ms || 1000);
    await sleep(ms);
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ waited_ms: ms }));
    return;
  }

  res.writeHead(404, { "content-type": "application/json" });
  res.end(JSON.stringify({ error: "not found" }));
});

const port = process.env.PORT || 3000;
server.listen(port, () => {
  console.log(`HTTP server listening on http://localhost:${port}`);
});
