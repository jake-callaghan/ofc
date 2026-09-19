export function invitation(text) {
  let value;
  try {
    const url = new URL(text.trim());
    const compact = /^#join\/([A-Za-z0-9_-]{22})\/([A-Za-z0-9_-]+)$/.exec(
      url.hash,
    );
    if (compact) {
      const bytes = atob(
        compact[1].replaceAll('-', '+').replaceAll('_', '/') + '==',
      );
      if (bytes.length !== 16) throw new Error();
      const hex = Array.from(bytes, (byte) =>
        byte.charCodeAt(0).toString(16).padStart(2, '0'),
      ).join('');
      value = {
        game: `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`,
        invite: compact[2],
      };
    } else {
      value = JSON.parse(new URLSearchParams(url.hash.slice(1)).get('join'));
    }
  } catch {
    throw new Error('Paste a complete invitation link.');
  }
  if (
    !value ||
    typeof value.game !== 'string' ||
    typeof value.invite !== 'string'
  )
    throw new Error('Paste a complete invitation link.');
  return value;
}

export function invitationLink(base, game, invite) {
  const hex = game.replaceAll('-', '');
  if (!/^[0-9a-f]{32}$/i.test(hex) || !/^[A-Za-z0-9_-]+$/.test(invite)) {
    throw new Error('Invalid invitation details.');
  }
  const bytes = hex
    .match(/../g)
    .map((pair) => String.fromCharCode(parseInt(pair, 16)))
    .join('');
  const compact = btoa(bytes)
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replaceAll('=', '');
  const url = new URL(base);
  url.search = '';
  url.hash = `join/${compact}/${invite}`;
  return url.href;
}

export function route() {
  const params = new URLSearchParams(location.hash.slice(1));
  return {
    id: params.get('game'),
    join:
      params.has('join') || location.hash.startsWith('#join/')
        ? location.href
        : null,
  };
}
