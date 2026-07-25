const http = require('http');
const fs = require('fs');
const path = require('path');

const MIME = {
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.html': 'text/html',
    '.json': 'application/json',
    '.geojson': 'application/geo+json',
    '.gpkg': 'application/octet-stream',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
};

const ROOT = __dirname;

http.createServer((req, res) => {
    let url = req.url.split('?')[0];
    if (url === '/') url = '/index.html';
    const fp = path.join(ROOT, url);
    const ext = path.extname(fp);
    
    if (!fs.existsSync(fp)) {
        res.writeHead(404);
        return res.end('Not found');
    }
    
    const stat = fs.statSync(fp);
    res.writeHead(200, {
        'Content-Type': MIME[ext] || 'text/plain',
        'Content-Length': stat.size,
        'Access-Control-Allow-Origin': '*',
    });
    
    fs.createReadStream(fp).pipe(res);
    
    const sizeKB = (stat.size / 1024).toFixed(1);
    console.log(`200 GET ${url} (${sizeKB} KB)`);
}).listen(8080, () => console.log('Server: http://localhost:8080'));
