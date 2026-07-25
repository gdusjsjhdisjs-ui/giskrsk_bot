const https = require('https');
const key = '073b03cc7ee19378c5b78d9c0ad70890';

const LAYER_NAMES = [
  // pkk variants
  'pkk', 'pkk_ngrr1', 'pkk_ngrr2', 'pkk_ngrr3', 'pkk_ngrr4',
  // zouit / zoouit
  'zoouit', 'zouit', 'zouit_bereg', 'zkz', 'oks', 'zu',
  // cadastre variants
  'cadastre', 'kadastr', 'cadastre_fill', 'cadastre_polygons', 'cadastre_line',
  'parcels', 'parcels_polygons', 'parcels_line', 'parcels_fill',
  // rosreestr
  'rosreestr', 'egrn', 'nspd',
  // russia specific
  'russia', 'rf', 'region', 'krai', 'krasnoyarsk',
  // geography
  'relief', 'hillshade', 'contour', 'hybrid',
  // water/forest
  'water', 'forest', 'green', 'vegetation',
  // transport
  'road', 'railway', 'transport',
  // admin
  'admin', 'boundary', 'border',
  // buildings
  'building', 'buildings', 'house', 'address',
  // other common
  'landcover', 'landuse', 'soil',
  'geology', 'mineral',
  'heatmap', 'population', 'density',
  // NextGIS specific
  'ngw', 'nextgis', 'demo',
  // ZOUIT detailed
  'zoouit_line', 'zoouit_polygon', 'zoouit_point',
  'zouit_line', 'zouit_polygon', 'zouit_point',
  // EGRN / Rosreestr detailed
  'egrn_zkz', 'egrn_oks', 'egrn_zu', 'egrn_zouit',
  'rosreestr_zkz', 'rosreestr_oks', 'rosreestr_zu', 'rosreestr_zouit',
  // kadastr variants
  'kadastr_zkz', 'kadastr_oks', 'kadastr_zu', 'kadastr_zouit',
  // zones
  'zone', 'zones', 'pzz',
  // plan
  'plan', 'general_plan', 'genplan',
];

let total = LAYER_NAMES.length;
let done = 0;
const found = [];

function testLayer(name) {
  const BATCH = 10;
  // Try both /raster/ and /api/v1/tiles/ paths
  const paths = [
    '/raster/' + name + '/10/541/347.png',
    '/api/v1/tiles/' + name + '/10/541/347.png',
  ];
  
  let pathDone = 0;
  for (const path of paths) {
    const opts = {
      hostname: 'geoservices.nextgis.com',
      path: path + '?apikey=' + key,
      rejectUnauthorized: false,
      timeout: 5000,
    };
    const req = https.get(opts, (r) => {
      let d = '';
      r.on('data', (c) => { if (d.length < 500) d += c; });
      r.on('end', () => {
        const ct = r.headers['content-type'] || '';
        const isImage = ct.includes('image') || ct.includes('octet');
        if (isImage) {
          found.push({ name, path: path.split('/10/')[0], type: path.startsWith('/raster') ? 'raster' : 'tiles' });
          if (!found.find(x => x.name === name && x.path === path.split('/10/')[0])) {
            // avoid dupes in output
          }
        }
        pathDone++;
        done++;
        if (done === total) printResults();
      });
    });
    req.on('error', () => { pathDone++; done++; if (done === total) printResults(); });
    req.on('timeout', () => { req.destroy(); pathDone++; done++; if (done === total) printResults(); });
  }
}

function printResults() {
  console.log('\n=== Найдено работающих TMS слоёв ===\n');
  // Deduplicate
  const unique = {};
  for (const f of found) {
    const key = f.name + '@' + f.path;
    if (!unique[key]) unique[key] = f;
  }
  
  const raster = Object.values(unique).filter(f => f.type === 'raster');
  const tiles = Object.values(unique).filter(f => f.type === 'tiles');
  
  if (raster.length) {
    console.log('--- /raster/ (TMS) ---');
    for (const f of raster) console.log('  ✅ ' + f.path);
  }
  if (tiles.length) {
    console.log('\n--- /api/v1/tiles/ ---');
    for (const f of tiles) console.log('  ✅ ' + f.path);
  }
  
  if (!raster.length && !tiles.length) {
    console.log('  (ничего не найдено)');
  }
  
  console.log('\nПроверено вариантов: ' + total);
  console.log('Готово.');
}

// Start all requests
for (const name of LAYER_NAMES) {
  testLayer(name);
}
