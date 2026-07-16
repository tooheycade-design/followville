import { createReadStream, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = normalize(join(fileURLToPath(new URL("..", import.meta.url))));
const mime = {
  ".css": "text/css; charset=utf-8",
  ".glb": "model/gltf-binary",
  ".html": "text/html; charset=utf-8",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mp4": "video/mp4",
  ".png": "image/png",
  ".svg": "image/svg+xml"
};

createServer((request, response) => {
  const url = new URL(request.url || "/", "http://127.0.0.1");
  let pathname = decodeURIComponent(url.pathname);
  if (pathname === "/") pathname = "/index.html";
  if (pathname === "/today" || /^\/house\/\d+\/?$/.test(pathname)) pathname = "/town.html";
  const filePath = normalize(join(root, pathname.replace(/^\/+/, "")));
  if (!filePath.startsWith(root)) {
    response.writeHead(403).end("Forbidden");
    return;
  }
  try {
    const info = statSync(filePath);
    if (!info.isFile()) throw new Error("Not a file");
    response.writeHead(200, {
      "Cache-Control": "no-store",
      "Content-Length": info.size,
      "Content-Type": mime[extname(filePath).toLowerCase()] || "application/octet-stream"
    });
    if (request.method === "HEAD") response.end();
    else createReadStream(filePath).pipe(response);
  } catch {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }).end("Not found");
  }
}).listen(8765, "127.0.0.1", () => {
  process.stdout.write("Followville test server listening on http://127.0.0.1:8765\n");
});
