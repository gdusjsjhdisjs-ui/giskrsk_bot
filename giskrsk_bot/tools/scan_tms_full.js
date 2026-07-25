const https = require('https');
const key = '073b03cc7ee19378c5b78d9c0ad70890';

const names = [
  // уже знаем что работают
  'pkk/ngrr1', 'pkk/ngrr2',
  // zouit
  'zoouit', 'zouit', 'zouit_bereg', 'zkz', 'oks', 'zu',
  // pkk variants
  'pkk/ngrr3', 'pkk/ngrr4', 'pkk/ngrr', 'pkk',
  // rosreestr / egrn
  'egrn', 'nspd', 'rosreestr',
  'egrn/zkz', 'egrn/oks', 'egrn/zu', 'egrn/zouit',
  'rosreestr/zkz', 'rosreestr/oks', 'rosreestr/zu',
  // cadastre
  'cadastre', 'kadastr',
  'cadastre/fill', 'cadastre/line', 'cadastre/polygon',
  'parcels', 'parcels/fill', 'parcels/line',
  // common
  'relief', 'hillshade', 'hybrid', 'water', 'forest',
  'building', 'address', 'landcover', 'admin',
  'boundary', 'pzz', 'zone',
  // extended
  'pkk/ngrr1_fill', 'pkk/ngrr1_line', 'pkk/ngrr2_fill', 'pkk/ngrr2_line',
  'zoouit/fill', 'zoouit/line', 'zoouit/point',
  'zouit/fill', 'zouit/line',
  // more
  'heatmap', 'population',
  'krasnoyarsk', 'krai',
  'street', 'road',
  'contour', 'topo',
  'geology', 'soil',
];

let done = 0;
const found = [];
const total = names.length;

names.forEach(name => {
  const path = '/raster/' + name + '/10/541/347.png';
  const opts = {
    hostname: 'geoservices.nextgis.com',
    path: path + '?apikey=' + key,
    rejectUnauthorized: false,
    timeout: 8000,
  };
  const req = https.get(opts, (r) => {
    let d = '';
    r.on('data', c => { if (d.length < 500) d += c; });
    r.on('end', () => {
      const ct = r.headers['content-type'] || '';
      if (ct.includes('image') || ct.includes('octet')) {
        console.log('✅ /raster/' + name + ' [' + ct + ']');
        found.push(name);
      } else if (r.statusCode === 404) {
        // skip 404 silently
      } else if (r.statusCode === 200 && d.length > 2000 && !d.includes('<html')) {
        console.log('⚠ /raster/' + name + ' -> ' + r.statusCode + ' ' + d.substring(0, 80));
      }
      done++;
      if (done === total) { printResults(); }
    });
  });
  req.on('error', () => { done++; if (done === total) printResults(); });
  req.on('timeout', () => { req.destroy(); done++; if (done === total) printResults(); });
});

function printResults() {
  console.log('\n=== РЕЗУЛЬТАТ: работающих TMS слоёв: ' + found.length + ' ===\n');
  for (const f of found) {
    const url = 'https://geoservices.nextgis.com/raster/' + f + '/{z}/{x}/{y}.png?apikey=' + key;
    console.log("  { id: '" + f.replace('/', '_') + "', name: '???', type: 'tms', url: '" + url + "', visible: false },");
  }
  console.log('\nГотово.');
}
