const adjectives = [
  'Magical',
  'Fruity',
  'Cosmic',
  'Dancing',
  'Lucky',
  'Mischievous',
  'Sparkling',
  'Velvet',
  'Wobbly',
  'Golden',
  'Dreamy',
  'Jolly',
];

const nouns = [
  'Marble',
  'Spoon',
  'Panda',
  'Pineapple',
  'Teapot',
  'Otter',
  'Moon',
  'Waffle',
  'Flamingo',
  'Acorn',
  'Comet',
  'Pickle',
];

function pick(words) {
  return words[Math.floor(Math.random() * words.length)];
}

export function randomTableName(playerName) {
  return `${playerName.trim()}'s ${pick(adjectives)} ${pick(nouns)} Table`;
}
