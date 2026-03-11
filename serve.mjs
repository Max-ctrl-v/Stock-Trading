import { createServer } from 'http';
import { readFileSync, existsSync, statSync } from 'fs';
import { join, extname } from 'path';

const PORT = 1001;
const ROOT = import.meta.dirname;

const MIME = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

const server = createServer((req, res) => {
  let path = req.url.split('?')[0];
  if (path === '/') path = '/frontend/index.html';

  const filepath = join(ROOT, path);

  if (!existsSync(filepath) || !statSync(filepath).isFile()) {
    res.writeHead(404);
    res.end('Not Found');
    return;
  }

  const ext = extname(filepath);
  const mime = MIME[ext] || 'application/octet-stream';
  res.writeHead(200, { 'Content-Type': mime });
  res.end(readFileSync(filepath));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Serving at http://localhost:${PORT}`);
});
