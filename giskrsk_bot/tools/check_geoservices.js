const https = require('https');
const key = '073b03cc7ee19378c5b78d9c0ad70890';

function fetch(url) {
  return new Promise((res, rej) => {
    https.get(url, { rejectUnauthorized: false }, (r) => {
      let d = '';
      r.on('data', (c) => d += c);
      r.on('end', () => res({ status: r.statusCode, data: d, headers: r.headers }));
    }).on('error', rej);
  });
}

async function main() {
  console.log('=== Поиск URL тайлов в JS бандлах ===\n');
  
  const jsUrls = [
    'https://geoservices.nextgis.com/static/js/app.6a2610af.js',
  ];
  
  for (const url of jsUrls) {
    try {
      const r = await fetch(url);
      const data = r.data;
      console.log(url, data.length + 'b');
      
      // Ищем все URL с api/v1/tiles
      const re = /api\/v1\/tiles[^"'\\s]*/g;
      let m;
      let count = 0;
      while ((m = re.exec(data)) !== null && count < 10) {
        console.log('  Tiles path:', m[0]);
        count++;
      }
      // Ищем tileset ID
      const re2 = /tileset[^"'\\s]*/gi;
      while ((m = re2.exec(data)) !== null && count < 15) {
        console.log('  Tileset:', m[0]);
        count++;
      }
      if (count === 0) {
        // Ищем что-то про геосервисы
        const geoRe = /geoserv[^"'\\s]*/gi;
        let gc = 0;
        while ((m = geoRe.exec(data)) !== null && gc < 10) {
          console.log('  Geo:', m[0].substring(0, 80));
          gc++;
        }
      }
    } catch (e) {
      console.log('ERR:', url, e.message);
    }
  }
  
  // Также пробуем NextGIS Web API для поиска слоёв
  console.log('\n=== Проверка NextGIS Web ===');
  const ngwTests = [
    'https://zimin-maplive0000.nextgis.com/api/resource/?parent=0',
    'https://zimin-maplive0000.nextgis.com/api/component/auth/current_user/',
  ];
  for (const url of ngwTests) {
    try {
      const r = await fetch(url);
      console.log(r.status, url, r.data.substring(0, 200));
    } catch (e) {
      console.log('ERR:', e.message);
    }
  }
  
  console.log('\nDone');
}
main().catch(e => console.log(e));
