import express from "express";

const app = express();
app.use(express.json());

// Middleware: logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => {
    const ms = Date.now() - start;
    console.log(`${req.method} ${req.path} -> ${res.statusCode} (${ms}ms)`);
  });
  next();
});

app.get("/health", (req, res) => {
  res.json({ ok: true });
});

app.get("/hello", (req, res, next) => {
  const name = String(req.query.name || "").trim();
  if (!name) {
    const err = new Error("Missing query param: name");
    err.statusCode = 400;
    return next(err);
  }
  res.json({ message: `Hello, ${name}!` });
});

// Error middleware (must be last)
app.use((err, req, res, next) => {
  const status = err.statusCode || 500;
  res.status(status).json({ error: err.message });
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`Express server listening on http://localhost:${port}`);
});
