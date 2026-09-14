export function invitation(text) {
  const url = new URL(text);
  const value = JSON.parse(new URLSearchParams(url.hash.slice(1)).get('join'));
  if (
    !value ||
    typeof value.game !== 'string' ||
    typeof value.invite !== 'string'
  )
    throw new Error('Paste a complete invitation link.');
  return value;
}

export function route() {
  const params = new URLSearchParams(location.hash.slice(1));
  return {
    id: params.get('game'),
    join: params.has('join') ? location.href : null,
  };
}
