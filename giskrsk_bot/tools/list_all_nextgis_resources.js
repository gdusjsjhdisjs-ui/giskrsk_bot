const https = require('https');
const HOST = 'zimin-maplive0000.nextgis.com';

function get(path) {
  return new Promise((res, rej) => {
    const opts = { hostname: HOST, path, rejectUnauthorized: false };
    https.get(opts, (r) => {
      let d = '';
      r.on('data', (c) => d += c);
      r.on('end', () => {
        try { res(JSON.parse(d)); }
        catch (e) { res({ error: true, text: d.substring(0, 300) }); }
      });
    }).on('error', rej);
  });
}

async function fetchResource(id) {
  const data = await get('/api/resource/' + id);
  if (data.error) return null;
  
  const cls = data.resource?.cls;
  const name = data.resource?.display_name || '';
  
  const info = { id, cls, name };
  
  // Extract details based on type
  if (data.basemap_layer) {
    info.url = data.basemap_layer.url;
    info.qms = data.basemap_layer.qms;
  }
  if (data.tmsclient_connection) {
    info.connection = data.tmsclient_connection;
  }
  if (data.vector_layer) {
    info.geometry_type = data.vector_layer.geometry_type;
    info.feature_count = data.vector_layer.feature_count;
  }
  if (data.webmap) {
    info.root_resource = data.webmap.root_resource;
  }
  
  return info;
}

async function listChildren(parentId) {
  const data = await get('/api/resource/?parent=' + parentId);
  if (data.error || !Array.isArray(data)) return [];
  
  let results = [];
  for (const item of data) {
    const id = item.resource.id;
    const cls = item.resource.cls;
    const name = item.resource.display_name || '(unnamed)';
    
    results.push({ id, cls, name });
    
    // If it's a group, get children
    if (item.resource.children !== false && cls === 'resource_group') {
      const children = await listChildren(id);
      results = results.concat(children);
    }
  }
  return results;
}

async function main() {
  console.log('=== Сканирование всех ресурсов NextGIS Web ===\n');
  
  const all = [];
  const root = await get('/api/resource/?parent=0');
  
  for (const item of root) {
    const id = item.resource.id;
    const cls = item.resource.cls;
    const name = item.resource.display_name || '(unnamed)';
    
    all.push({ id, cls, name });
    
    if (item.resource.children !== false && cls === 'resource_group') {
      const children = await listChildren(id);
      for (const c of children) {
        all.push(c);
      }
    }
  }
  
  // Также явно проверим корневые ресурсы (без parent=0)
  const root2 = await get('/api/resource/');
  if (Array.isArray(root2)) {
    for (const item of root2) {
      const id = item.resource?.id;
      if (id && !all.find(x => x.id === id)) {
        all.push({ id, cls: item.resource.cls, name: item.resource.display_name || '' });
      }
    }
  }
  
  // Детально каждый ресурс
  console.log('Найдено ресурсов:', all.length);
  console.log('────────────────────────────────────────────────────────');
  
  for (const r of all) {
    // Для vector_layer, basemap_layer, tmsclient - получаем детали
    if (['vector_layer', 'basemap_layer', 'tmsclient_layer', 'tmsclient_connection', 'webmap', 'raster_layer', 'postgis_layer', 'wmsserver_layer', 'wfsclient_layer', 'tracker_layer'].includes(r.cls)) {
      const detail = await fetchResource(r.id);
      console.log(`\n[${r.id}] ${r.cls}`);
      console.log(`  Имя: ${r.name}`);
      if (detail?.url) console.log(`  URL: ${detail.url}`);
      if (detail?.qms) {
        try { const q = JSON.parse(detail.qms); console.log(`  QMS: z=${q.z_min}-${q.z_max}, epsg=${q.epsg}`); } catch(e) {}
      }
      if (detail?.feature_count) console.log(`  Объектов: ${detail.feature_count}`);
      if (detail?.geometry_type) console.log(`  Геометрия: ${detail.geometry_type}`);
      if (detail?.root_resource) console.log(`  Root resource: ${detail.root_resource}`);
    } else if (['basemap_layer', 'tmsclient_layer'].includes(r.cls)) {
      // still need details
    } else {
      console.log(`[${r.id}] ${r.cls} ${r.name ? '— ' + r.name : ''}`);
    }
  }
  
  // Специально проверим basemap_layer 320 (2gis) и 133 (Google Satellite)
  console.log('\n\n=== Детали basemap слоёв ===');
  for (const bid of [133, 191, 320]) {
    const d = await fetchResource(bid);
    if (d) console.log(`\n[${bid}] ${d.name}:`, JSON.stringify(d, null, 2).substring(0, 300));
  }
  
  // Проверим TMS слой 47
  console.log('\n=== TMS Layer (id:47) ===');
  const tmsLayer = await get('/api/resource/47');
  console.log(JSON.stringify(tmsLayer, null, 2).substring(0, 500));
  
  console.log('\nDone.');
}
main().catch(e => console.log(e));
