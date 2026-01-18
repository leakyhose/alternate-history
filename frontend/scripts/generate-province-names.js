const fs = require('fs');
const path = require('path');

const csvPath = path.join(__dirname, '../public/raw_data/definition.csv');
const outputPath = path.join(__dirname, '../public/province-names.json');

const csv = fs.readFileSync(csvPath, 'utf8');
const lines = csv.split('\n');
const names = {};

for (let i = 1; i < lines.length; i++) {
  const parts = lines[i].split(';');
  if (parts.length >= 5 && parts[0]) {
    const id = parseInt(parts[0]);
    const name = parts[4];
    if (!isNaN(id) && name && name !== 'x') {
      names[id] = name;
    }
  }
}

fs.writeFileSync(outputPath, JSON.stringify(names));
console.log('Created province-names.json with', Object.keys(names).length, 'provinces');
