const fs = require('fs');
const path = require('path');
const iconv = require('iconv-lite');

// Map of accented characters to ASCII equivalents
const translitMap = {
  'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A', 'Å': 'A', 'Æ': 'AE',
  'Ç': 'C', 'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E',
  'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I',
  'Ð': 'D', 'Ñ': 'N',
  'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O', 'Ø': 'O',
  'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U',
  'Ý': 'Y', 'Þ': 'TH', 'ß': 'ss',
  'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a', 'æ': 'ae',
  'ç': 'c', 'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
  'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
  'ð': 'd', 'ñ': 'n',
  'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o', 'ø': 'o',
  'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
  'ý': 'y', 'þ': 'th', 'ÿ': 'y',
  'Œ': 'OE', 'œ': 'oe', 'Š': 'S', 'š': 's', 'Ž': 'Z', 'ž': 'z',
  'ƒ': 'f', 'Ÿ': 'Y'
};

function transliterate(str) {
  return str.split('').map(char => translitMap[char] || char).join('');
}

const csvPath = path.join(__dirname, '../public/raw_data/definition.csv');
const outputPath = path.join(__dirname, '../public/province-names.json');

// Read file as binary buffer, then decode as Latin-1 (ISO-8859-1)
const buffer = fs.readFileSync(csvPath);
const csv = iconv.decode(buffer, 'latin1');

const lines = csv.split('\n');
const names = {};

for (let i = 1; i < lines.length; i++) {
  const parts = lines[i].split(';');
  if (parts.length >= 5 && parts[0]) {
    const id = parseInt(parts[0]);
    let name = parts[4];
    if (!isNaN(id) && name && name !== 'x') {
      // Transliterate to ASCII
      name = transliterate(name.trim());
      names[id] = name;
    }
  }
}

fs.writeFileSync(outputPath, JSON.stringify(names));
console.log('Created province-names.json with', Object.keys(names).length, 'provinces');
