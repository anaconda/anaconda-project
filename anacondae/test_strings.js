'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const files = [
  'sim.js',
  'server.js',
  ...fs.readdirSync(path.join(__dirname, 'public'))
    .filter((name) => fs.statSync(path.join(__dirname, 'public', name)).isFile())
    .map((name) => path.join('public', name)),
];
const thirdParties = [
  'PyPI',
  'Hugging Face',
  'OpenAI',
  'Anthropic',
  'GitHub',
  'GitLab',
  'Docker Hub',
  'TensorFlow',
  'PyTorch',
];

for (const file of files) {
  const source = fs.readFileSync(path.join(__dirname, file), 'utf8');
  for (const name of thirdParties) {
    assert(!new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(source), `${file} contains denied third-party name: ${name}`);
  }
  assert(!/(?<!Dev )AI Factory/i.test(source), `${file} contains AI Factory without Dev`);
  assert(!/main-x|#3DAE2B|Poppins/i.test(source), `${file} contains a superseded product or brand token`);
}

console.log('test_strings: ok');
