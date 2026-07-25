const fs = require('fs');
const path = require('path');

const DESKTOP = path.join(require('os').homedir(), 'Desktop');
const GIS_PROJECT = path.join(DESKTOP, 'ГИС Красноярск проект');
const GIS_BOT = path.join(DESKTOP, 'ГИС Красноярск проект', 'Данные для бота');
const TARGET = path.join(__dirname, '..', 'webapp', 'data');

console.log('=== Поиск реальных файлов ПЗЗ ===');
console.log('Папка проекта:', GIS_PROJECT);
console.log('Папка бота:', GIS_BOT);
console.log('Цель:', TARGET);

// Ищем большие GeoJSON/GPKG файлы
const found = [];

function walk(dir, depth = 0) {
    if (depth > 4) return;
    try {
        const entries = fs.readdirSync(dir);
        for (const f of entries) {
            const fp = path.join(dir, f);
            try {
                const s = fs.statSync(fp);
                if (s.isDirectory() && !f.startsWith('.')) {
                    walk(fp, depth + 1);
                } else if (s.size > 10000 && (f.endsWith('.geojson') || f.endsWith('.gpkg'))) {
                    found.push({ path: fp, size: s.size, name: f });
                    console.log(`  ${(s.size / 1024 / 1024).toFixed(2)} MB | ${fp}`);
                }
            } catch (e) { }
        }
    } catch (e) { }
}

walk(GIS_PROJECT);

// Ищем также рядом с ботом
const BOT_SRC = path.join(GIS_BOT);
try {
    fs.readdirSync(BOT_SRC).forEach(f => {
        const fp = path.join(BOT_SRC, f);
        try {
            const s = fs.statSync(fp);
            if (s.size > 10000 && (f.endsWith('.geojson') || f.endsWith('.gpkg'))) {
                if (!found.find(x => x.path === fp)) {
                    found.push({ path: fp, size: s.size, name: f });
                    console.log(`  ${(s.size / 1024 / 1024).toFixed(2)} MB | ${fp}`);
                }
            }
        } catch (e) { }
    });
} catch (e) {
    console.log('Папка Данные для бота не найдена');
}

// Ищем прямо на рабочем столе
try {
    fs.readdirSync(DESKTOP).forEach(f => {
        const fp = path.join(DESKTOP, f);
        try {
            const s = fs.statSync(fp);
            if (s.size > 10000 && (f.endsWith('.geojson') || f.endsWith('.gpkg'))) {
                if (!found.find(x => x.path === fp)) {
                    found.push({ path: fp, size: s.size, name: f });
                    console.log(`  Desktop: ${(s.size / 1024 / 1024).toFixed(2)} MB | ${fp}`);
                }
            }
        } catch (e) { }
    });
} catch (e) { }

console.log('\n=== Найдено файлов:', found.length, '===');

if (found.length === 0) {
    console.log('Файлы не найдены!');
    process.exit(1);
}

// Создаём целевую папку
try { fs.mkdirSync(TARGET, { recursive: true }); } catch (e) { }

// Копируем самые релевантные файлы
const PZZ_MAP = {
    'pzz_krasnoyarsk': 'pzz_krasnoyarsk.geojson',
    'pzz_emelyanovsky': 'pzz_emelyanovsky.geojson',
    'pzz_divnogorsk': 'pzz_divnogorsk.geojson',
    'pzz_sosnovoborsk': 'pzz_sosnovoborsk.geojson',
    'пзз_красноярск': 'pzz_krasnoyarsk.geojson',
};

const copied = [];
for (const file of found) {
    const name = file.name.toLowerCase().replace(/\.(geojson|gpkg)$/, '');
    const targetName = PZZ_MAP[name] || file.name;
    const targetPath = path.join(TARGET, targetName);

    // Проверяем, копировали ли уже такой файл
    if (copied.includes(targetName)) continue;

    try {
        fs.copyFileSync(file.path, targetPath);
        copied.push(targetName);
        console.log(`✅ КОПИРОВАН: ${file.name} → ${targetPath} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
    } catch (e) {
        console.log(`❌ ОШИБКА копирования ${file.name}: ${e.message}`);
    }
}

console.log(`\n=== Скопировано файлов: ${copied.length} ===`);
